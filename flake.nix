{
  description = "forge-triage — fast TUI for triaging GitHub notifications";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs =
    { nixpkgs, ... }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-darwin"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      pkgsFor = system: nixpkgs.legacyPackages.${system};
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          python = pkgs.python313;
        in
        {
          default = python.pkgs.buildPythonApplication {
            pname = "forge-triage";
            version = "0.1.0";
            pyproject = true;

            src = ./.;

            build-system = [ python.pkgs.hatchling ];

            dependencies = with python.pkgs; [
              textual
              httpx
            ];

            nativeCheckInputs = with python.pkgs; [
              pytestCheckHook
              pytest-asyncio
              pytest-httpx
              pytest-xdist
            ];

            meta = {
              description = "Fast TUI for triaging GitHub notifications";
              mainProgram = "forge-triage";
            };
          };
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          python = pkgs.python313;
        in
        {
          default = pkgs.mkShell {
            packages = [
              (python.withPackages (
                ps: with ps; [
                  textual
                  httpx
                  pytest
                  pytest-asyncio
                  pytest-httpx
                  pytest-xdist
                  mypy
                ]
              ))
              pkgs.ruff
            ];
          };
        }
      );
    };
}
