-- EPI-LEAN environment dump utility (Lean 4.15, no Mathlib).
--
-- Writes one JSON object per line (JSONL) with every *user* declaration
-- of the target module: name, kind, direct dependencies (names used in
-- type and value expressions), and the axioms its proof depends on,
-- computed with Lean's own `collectAxioms` (transitive, kernel-level).
--
-- Usage:
--   lake env lean --run tools/EpiDump.lean -- out.jsonl <Root.Module> [more modules...]
--
-- The module names given after the output path are imported (from the
-- project's compiled .olean files via LEAN_PATH), and declarations whose
-- module index matches those target modules are dumped. Compiler
-- artifacts (names ending in `_cstage1/2`, `match_1..n`, or containing
-- `._eq_`/`.sizeOf_spec` style internals) are excluded.
--
-- This is an *elaborated-environment* extraction: names and dependency
-- edges come from Lean itself after elaboration, so they are exact for
-- any project, including Mathlib-scale ones.

import Lean
open Lean

/-- Minimal monad with a `MonadEnv` instance so `collectAxioms` can run
from plain IO without setting up a full `CoreM` context. -/
abbrev EnvM (α : Type) := ReaderT Environment (EIO Exception) α

instance : MonadEnv EnvM where
  getEnv := read
  modifyEnv _ := pure ()

/-- Axioms a constant's proof depends on (transitive closure), computed
by Lean's own `collectAxioms` — a kernel-level query, not a heuristic. -/
def axiomsOf (env : Environment) (name : Name) : IO (Array Name) := do
  let step : EnvM (Array Name) := collectAxioms name
  let out ← (step.run env).toIO'
  match out with
  | .ok axs => pure axs
  | .error e => do
      let msg ← e.toMessageData.toString
      throw <| IO.userError s!"collectAxioms failed for '{name}': {msg}"

/-- Kind of a constant, mapped from its `ConstantInfo` variant. -/
def constantKind (ci : ConstantInfo) : String :=
  match ci with
  | .axiomInfo _ => "axiom"
  | .defnInfo _ => "def"
  | .thmInfo _ => "theorem"
  | .opaqueInfo _ => "opaque"
  | .ctorInfo _ => "ctor"
  | .inductInfo _ => "inductive"
  | .quotInfo _ => "quot"
  | .recInfo _ => "recursor"

/-- JSON-escape a string: backslash and quote doubling. -/
def jsonEscape (s : String) : String :=
  (s.replace "\\" "\\\\").replace "\"" "\\\""

/-- Render a name unescaped, then JSON-escape it. -/
def nameToJson (n : Name) : String :=
  jsonEscape (n.toString (escape := false))

/-- True when a `.` appears anywhere in the rendered name. -/
def nameHasDot (s : String) : Bool :=
  s.data.foldl (fun acc c => acc || c == '.') false

/-- True for compiler-generated artifacts that should not appear in the
audit as user declarations (staging defs, match equations, aux decls). -/
def isCompilerArtifact (name : Name) : Bool :=
  let s := name.toString (escape := false)
  s.endsWith "_cstage1"
  || s.endsWith "_cstage2"
  || s.endsWith "_cstage3"
  || s.startsWith "_example."
  || s.startsWith "_cmd."
  || s.endsWith "_auxLemma"
  || (s.startsWith "match_" && !nameHasDot s)

/-- Serialize one constant as a single JSON line. -/
def constantToJsonLine (env : Environment) (name : Name) (ci : ConstantInfo) :
    IO String := do
  let kind := constantKind ci
  let typeUsed : Array Name := ci.type.getUsedConstants
  -- For theorems, ci.type is only the *statement*; the proof term
  -- (with its own constant references) is ThmVal.value.
  let valueUsed : Array Name :=
    match ci with
    | .defnInfo v => v.value.getUsedConstants
    | .thmInfo t => t.value.getUsedConstants
    | _ => #[]
  -- Direct dependencies: names in type/value that exist in the env.
  let depNames : Array Name :=
    (typeUsed.append valueUsed).filter fun n => env.contains n
  let depList : Array Name :=
    depNames.foldl (fun acc n =>
      if acc.contains n then acc else acc.push n) (#[] : Array Name)
      |>.qsort (fun a b => a.toString < b.toString)
  -- Axiom provenance: axioms report themselves; proof-carrying kinds
  -- get the transitive axiom closure from collectAxioms.
  let axioms : Array Name ←
    match ci with
    | .axiomInfo _ => pure #[name]
    | .thmInfo _ => axiomsOf env name
    | .defnInfo _ => axiomsOf env name
    | .opaqueInfo _ => axiomsOf env name
    | _ => pure #[]
  let depsStr : String :=
    String.intercalate ", "
      (depList.toList.map fun n => "\"" ++ nameToJson n ++ "\"")
  let axiomsStr : String :=
    String.intercalate ", "
      (axioms.toList.map fun n => "\"" ++ nameToJson n ++ "\"")
  let line : String := "{\"name\": \"" ++ nameToJson name ++ "\", \"kind\": \""
    ++ kind ++ "\", \"dependencies\": [" ++ depsStr ++ "], \"axioms\": ["
    ++ axiomsStr ++ "]}"
  return line

def main (args : List String) : IO Unit := do
  let outPath :=
    match args.head? with
    | some p => p
    | none => "epilean_dump.jsonl"
  let modNames : List Name :=
    (args.drop 1).map fun s => s.toName
  if modNames.isEmpty then
    throw <| IO.userError
      "usage: EpiDump.lean <out.jsonl> <Module.Name> [more...]"
  let mods : Array Import :=
    (modNames.map fun m => ({ module := m : Import })).toArray
  let env ← importModules mods Options.empty
  -- Module indices of the target modules: the module name itself is not
  -- a constant, so find its position in the header's module list.
  let headerMods : Array Name := env.header.moduleNames
  let targetIdxs : Array ModuleIdx :=
    (modNames.filterMap fun m =>
      match headerMods.findIdx? fun mn => mn == m with
      | some idx => some idx
      | none => none).toArray
  if targetIdxs.isEmpty then
    throw <| IO.userError
      "none of the given modules were found in the environment"
  let isTarget : Name → Bool := fun name =>
    match env.getModuleIdxFor? name with
    | some idx => targetIdxs.contains idx
    | none => false
  IO.println s!"EPI-LEAN dump: writing to {outPath}"
  let handle ← IO.FS.Handle.mk outPath .write
  let mut count : Nat := 0
  for (name, ci) in env.constants.toList do
    if isTarget name && !isCompilerArtifact name then
      let line ← constantToJsonLine env name ci
      handle.putStrLn line
      count := count + 1
  IO.println s!"EPI-LEAN dump: wrote {count} constants"
