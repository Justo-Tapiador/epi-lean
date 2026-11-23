import Lake
open Lake DSL

package «epiTest» where

@[default_target]
lean_lib «EpiTest» where
  roots := #[`EpiTest.Test]
