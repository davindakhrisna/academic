{
  description = "Python & UV development environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    systems = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
  in {
    devShells = forAllSystems (pkgs: {
      default = pkgs.mkShell {
        packages = with pkgs; [
          python3
          uv
          ruff
          pyright
          black
        ];

        shellHook = ''
          export VIRTUAL_ENV="$PWD/.direnv/venv"
          if [ ! -d "$VIRTUAL_ENV" ]; then
            uv venv "$VIRTUAL_ENV" --quiet
          fi
          if [ -d "$VIRTUAL_ENV" ]; then
            # shellcheck disable=SC1091
            source "$VIRTUAL_ENV/bin/activate"
          fi
          echo "⚡ [Python & UV Dev Environment Loaded]"
          echo "  • Python: $(python3 --version 2>/dev/null || echo 'ready')"
          echo "  • uv:     $(uv --version 2>/dev/null || echo 'ready')"
          echo "  • Venv:   $VIRTUAL_ENV"
        '';
      };
    });
  };
}
