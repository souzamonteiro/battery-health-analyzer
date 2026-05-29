#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

install_ubuntu() {
	echo "Detected Ubuntu Linux. Installing dependencies with apt (unchanged behavior)."
	sudo apt update
	sudo apt install -y python3-pandas python3-sklearn python3-matplotlib python3-tk
}

install_macos() {
	echo "Detected macOS. Installing dependencies with Homebrew."
	if ! command -v brew >/dev/null 2>&1; then
		echo "Homebrew is required on macOS. Install it first from https://brew.sh/"
		exit 1
	fi

	brew update
	# Homebrew provides Python runtime and Tk bindings.
	brew install python tcl-tk

	if command -v python3 >/dev/null 2>&1; then
		# Homebrew Python is PEP 668 managed; --break-system-packages is required for global pip installs.
		sudo -H python3 -m pip install --upgrade pip --break-system-packages
		sudo -H python3 -m pip install --break-system-packages pandas scikit-learn matplotlib
	else
		echo "python3 was not found after Homebrew install."
		exit 1
	fi
}

install_windows() {
	echo "Detected Windows shell environment. Installing dependencies with pip."
	if command -v py >/dev/null 2>&1; then
		py -m pip install --upgrade pip
		py -m pip install pandas scikit-learn matplotlib
	elif command -v python >/dev/null 2>&1; then
		python -m pip install --upgrade pip
		python -m pip install pandas scikit-learn matplotlib
	else
		echo "Python was not found in PATH. Install Python 3 first."
		exit 1
	fi
}

install_other_linux() {
	echo "Detected non-Ubuntu Linux. Creating virtual environment and installing with pip."
	cd "$SCRIPT_DIR"

	if ! command -v python3 >/dev/null 2>&1; then
		echo "python3 is required but was not found."
		exit 1
	fi

	python3 -m venv .venv
	# shellcheck disable=SC1091
	source .venv/bin/activate
	python -m pip install --upgrade pip
	python -m pip install pandas scikit-learn matplotlib

	echo "Virtual environment ready at $SCRIPT_DIR/.venv"
	echo "Activate it with: source .venv/bin/activate"
}

case "$(uname -s)" in
	Darwin)
		install_macos
		;;
	Linux)
		if [ -f /etc/os-release ] && grep -qi 'ubuntu' /etc/os-release; then
			install_ubuntu
		else
			install_other_linux
		fi
		;;
	MINGW*|MSYS*|CYGWIN*|Windows_NT)
		install_windows
		;;
	*)
		echo "Unsupported OS: $(uname -s)"
		exit 1
		;;
esac

echo "Dependency installation completed."
