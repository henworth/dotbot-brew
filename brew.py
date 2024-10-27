import dotbot
import platform
import subprocess


class Brew(dotbot.Plugin):
    _brew_directive = "brew"
    _brewfile_directive = "brewfile"
    _cask_directive = "cask"
    _tap_directive = "tap"
    _install_url = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"

    # From https://docs.brew.sh/Installation these are the default and recommended
    # installation paths.
    if platform.sys.platform == "darwin":
        _is_macos = True
        _homebrew_path = "/usr/local"
        if platform.machine() == "arm64":
            _homebrew_path = "/opt/homebrew"
    elif platform.sys.platform == "linux":
        _is_macos = False
        _homebrew_path = "/home/linuxbrew/.linuxbrew"

    # Construct the env vars that `brew shellenv` returns
    _homebrew_envs = {
        "HOMEBREW_PREFIX": _homebrew_path,
        "HOMEBREW_CELLAR": f"{_homebrew_path}/Cellar",
        "HOMEBREW_REPOSITORY": _homebrew_path,
        "PATH": f"{_homebrew_path}/bin:{_homebrew_path}/sbin${{PATH+:$PATH}}",
        "MANPATH": f"{_homebrew_path}/share/man${{MANPATH+:$MANPATH}}:",
        "INFOPATH": f"{_homebrew_path}/share/info:${{INFOPATH:-}}",
    }

    def can_handle(self, directive):
        directives = [
            self._tap_directive,
            self._brew_directive,
            self._brewfile_directive,
        ]

        if self._is_macos:
            directives.append(self._cask_directive)

        return directive in tuple(directives)

    def handle(self, directive, data):
        if not self.can_handle(directive):
            raise ValueError(f"Brew cannot handle directive {directive}")

        try:
            self._run_cmd("hash brew", capture_output=False)
        except subprocess.CalledProcessError:
            self._log.info("Brew not found, installing")
            self._bootstrap_brew()

        if self._is_macos:
            self._run_cmd("brew tap homebrew/cask")

        match directive:
            case self._tap_directive:
                return self._tap(data)
            case self._brew_directive:
                return self._process_data("brew install", data)
            case self._cask_directive:
                return self._process_data("brew install --cask", data)
            case self._brewfile_directive:
                return self._install_bundle(data)

    def _run_cmd(self, cmd, capture_output=True, include_envs=True):
        if include_envs:
            cmd = f'eval "$({self._homebrew_envs})" && {cmd}'
        self._log.lowinfo(cmd)
        return subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=capture_output,
            cwd=self._context.base_directory(),
        )

    def _bootstrap_brew(self):
        try:
            self._run_cmd(
                f'/bin/bash -c "$(curl -fsSL {self._install_url})"', include_envs=False
            )
        except subprocess.CalledProcessError:
            self._log.warning("Brew could not be installed")
        else:
            self._log.info("Updating brew")
            try:
                self._run_cmd("brew update")
            except subprocess.CalledProcessError:
                self._log.warning("Brew could not be updated")

    def _tap(self, tap_list):
        for tap in tap_list:
            self._log.info(f"Tapping {tap}")
            try:
                self._run_cmd(f"brew tap {tap}")
            except subprocess.CalledProcessError as e:
                self._log.warning(f"Failed to tap [{tap}] - {e}")
                return False
        return True

    def _process_data(self, install_cmd, data):
        install_type = "casks" if "--cask" in install_cmd else "formulae"
        success = self._install(install_cmd, data)
        if success:
            self._log.info(f"All brew {install_type} have been installed")
        else:
            self._log.error(f"Some brew {install_type} were not installed")
        return success

    def _install(self, install_cmd, packages_list):
        cask_flag = "--cask" if install_cmd != "brew install" else ""
        for package in packages_list:
            try:
                self._run_cmd(f"brew ls --versions {cask_flag} {package}")
            except subprocess.CalledProcessError:
                self._log.info(f"Installing {package}")
                try:
                    self._run_cmd(f"{install_cmd} {cask_flag} {package}")
                except subprocess.CalledProcessError as e:
                    self._log.warning(f"Failed to install [{package}] - {e}")
                    return False
        return True

    def _install_bundle(self, brew_files):
        for brew_file in brew_files:
            self._log.info(f"Installing from file {brew_file}")
            try:
                self._run_cmd(f"brew bundle --file={brew_file}")
            except subprocess.CalledProcessError as e:
                self._log.warning(f"Failed to install file [{brew_file}] - {e}")
                return False
        return True
