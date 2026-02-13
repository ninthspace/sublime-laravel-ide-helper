import sublime
import sublime_plugin
import subprocess
import os
import threading
import json


def _shell_env():
    """Get a full shell environment so subprocess can find composer/php."""
    env = os.environ.copy()
    try:
        path = subprocess.check_output(
            ["/bin/zsh", "-lc", "echo $PATH"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        env["PATH"] = path
    except (subprocess.CalledProcessError, OSError):
        pass
    return env


_ENV = _shell_env()


class IdeHelperOnProjectOpen(sublime_plugin.EventListener):
    """Detect Laravel projects and manage ide-helper on project open."""

    _checked_roots = set()

    def on_activated_async(self, view):
        window = view.window()
        if not window:
            return

        folders = window.folders()
        if not folders:
            return

        root = folders[0]
        if root in self._checked_roots:
            return

        artisan = os.path.join(root, "artisan")
        if not os.path.isfile(artisan):
            return

        self._checked_roots.add(root)
        t = threading.Thread(target=self._check, args=(root, window))
        t.daemon = True
        t.start()

    @staticmethod
    def _check(root, window):
        composer_json = os.path.join(root, "composer.json")
        if not os.path.isfile(composer_json):
            return

        try:
            with open(composer_json, "r") as f:
                data = json.load(f)
        except (ValueError, OSError):
            return

        require_dev = data.get("require-dev", {})
        has_package = "barryvdh/laravel-ide-helper" in require_dev

        if not has_package:
            sublime.set_timeout(
                lambda: _prompt_install(window, root), 0
            )
            return

        # Package is installed — run ide-helper generation in background
        sublime.status_message("IDE Helper: refreshing...")
        try:
            subprocess.call(
                ["composer", "run", "post-update-cmd"],
                cwd=root,
                env=_ENV,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            sublime.status_message("IDE Helper: ready")
        except OSError:
            sublime.status_message("IDE Helper: composer not found")


def _prompt_install(window, root):
    items = [
        "Install barryvdh/laravel-ide-helper and configure composer.json",
        "Skip for this session",
    ]

    def on_select(index):
        if index == 0:
            t = threading.Thread(target=_install_and_configure, args=(root,))
            t.daemon = True
            t.start()

    window.show_quick_panel(items, on_select)


def _install_and_configure(root):
    sublime.status_message("IDE Helper: installing...")

    try:
        proc = subprocess.Popen(
            ["composer", "require", "--dev", "barryvdh/laravel-ide-helper"],
            cwd=root,
            env=_ENV,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, stderr = proc.communicate()
    except OSError:
        sublime.status_message("IDE Helper: composer not found")
        return

    if proc.returncode != 0:
        sublime.status_message("IDE Helper: composer require failed")
        return

    # Add ide-helper commands to post-update-cmd in composer.json
    composer_json = os.path.join(root, "composer.json")
    try:
        with open(composer_json, "r") as f:
            data = json.load(f)

        scripts = data.setdefault("scripts", {})
        post_update = scripts.setdefault("post-update-cmd", [])

        ide_commands = [
            "@php artisan ide-helper:generate",
            "@php artisan ide-helper:models -N",
            "@php -d memory_limit=512M artisan ide-helper:meta",
        ]
        for cmd in ide_commands:
            if cmd not in post_update:
                post_update.append(cmd)

        with open(composer_json, "w") as f:
            json.dump(data, f, indent=4)
            f.write("\n")
    except (ValueError, OSError):
        sublime.status_message("IDE Helper: failed to update composer.json")
        return

    # Add generated files to .gitignore
    gitignore = os.path.join(root, ".gitignore")
    ignore_entries = ["_ide_helper.php", "_ide_helper_models.php", ".phpstorm.meta.php"]
    try:
        existing = ""
        if os.path.isfile(gitignore):
            with open(gitignore, "r") as f:
                existing = f.read()

        to_add = [e for e in ignore_entries if e not in existing]
        if to_add:
            with open(gitignore, "a") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write("\n".join(to_add) + "\n")
    except OSError:
        pass

    # Generate the helper files
    sublime.status_message("IDE Helper: generating files...")
    try:
        subprocess.call(
            ["composer", "run", "post-update-cmd"],
            cwd=root,
            env=_ENV,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        sublime.status_message("IDE Helper: installed and ready")
    except OSError:
        sublime.status_message("IDE Helper: composer not found")
