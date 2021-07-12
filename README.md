![logo](https://github.com/ZENALC/algobot/blob/master/media/algobot.png?raw=true)

[![CI](https://github.com/ZENALC/algobot/actions/workflows/ci.yml/badge.svg)](https://github.com/ZENALC/algobot/actions/workflows/ci.yml)
[![CodeQL](https://github.com/ZENALC/algobot/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/ZENALC/algobot/actions/workflows/codeql-analysis.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-370/)
![Discord](https://img.shields.io/discord/863916085832974346)

Cryptocurrency trading bot that allows users to create strategies and then backtest, optimize, simulate, or run live bots using them. Telegram integration has been added to support easier and remote trading.

# Installation

Algobot requires at least Python 3.7.

Once you have cloned or unpacked the source code locally, run the following commands from your terminal in that directory.

For Linux/MacOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For Windows:

```bash
python -m venv venv
call venv/Scripts/activate
pip install -r requirements.txt
```

If your install fails, please make sure to have [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2019) installed.

# Execution

To run Algobot, run `python -m algobot` from within the activated virtual environment.

Set `DEBUG=1` to enable debug level logging.

# Community

Join our [Discord](https://discord.gg/ZWdHxhVbNP) today for contributions or help!

# Features

- View real time data.
- Create graphs with real time data and/or moving averages.
- Run simulations with parameters configured.
- Run custom backtests with parameters configured.
- Run live bots with parameters configured.
- Telegram integration that allows users to trade or view statistics.
- Create custom, trailing, or limit stop losses.
- Create take profits.
- Optimize your strategies using the built-in optimizer. \
- Ability to create your own custom strategies.

# User Interface

![Main Interface](https://i.imgur.com/Y6FD5O5.png)
![Configuration](https://i.imgur.com/JTvHRXf.png)
![Graphs](https://i.imgur.com/M9Oz3Q6.png)
![News](https://i.imgur.com/Ec6Tw17.png)

# Disclaimer

Bot usage is as is. Algobot is not responsible for any financial burdens or unexpected monetary bugs or glitches.

# License

GNU General Public License v3.0

# Author

Mihir Shrestha

# Contributors

koutsie, Malachi Soord (inverse)

# Special Contributors

Peter Motin for being the founder and head of strategic development throughout the entirety of this project.

# Contribution

Check our [contributing guidelines](CONTRIBUTING.md) to get started.

# Feature Requests

For any feature requests, feel free to add a feature request through Github's Issues. We would love to hear your ideas and implement them on the application.

# Wiki

You can find documentation regarding Algobot [here](https://github.com/ZENALC/algobot/wiki).
