![logo](https://github.com/ZENALC/algobot/blob/master/media/algobot.png?raw=true)

[![CI](https://github.com/ZENALC/algobot/actions/workflows/ci.yml/badge.svg)](https://github.com/ZENALC/algobot/actions/workflows/ci.yml)
[![CodeQL](https://github.com/ZENALC/algobot/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/ZENALC/algobot/actions/workflows/codeql-analysis.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-370/)
![Discord](https://img.shields.io/discord/863916085832974346)

사용자가 전략을 만든 다음 이를 사용하여 라이브 봇을 백테스트, 최적화, 시뮬레이션 또는 실행할 수 있는 암호 화폐 거래 봇입니다. 텔레그램 통합은 더 쉬운 지원과 원격 거래를 위해 추가되었습니다.

Algobot은 최소한 Python 3.7버전이 필요합니다.

<hr>

Algobot에는 TA-LIB가 필요하다는 것을 참고하세요.  [여기서](https://github.com/mrjbq7/ta-lib) TA-LIB 다운로드 방법에 대한 지침을 볼 수 있습니다. Windows 사용자의 경우, 파이썬 설치용 .whl 패키지를 다운로드하고 `pip install` 하는 것이 가장 좋습니다. Linux 및 MacOS 사용자의 경우, 위에 제공된 링크에 사용가능한 우수한 설명서가 존재합니다.

<hr>

소스 코드를 로컬에서 복제하거나 압축을 풀면, 해당 디렉터리의 터미널에서 다음 명령을 실행합니다.

```bash
pip install pipenv
pipenv install --dev
```

만약 설치에 실패하면 [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2019)이 설치되어 있는지 확인하세요. 

# 실행

Algobot을 시작하기 위해서, 실행하세요:

```bash
pipenv run python -m algobot
```

디버그 수준 로깅을 사용할수 있도록 `DEBUG=1` 을 설정하세요

# 소통

기여나 도움을 위해 우리의 [디스코드](https://discord.gg/ZWdHxhVbNP)에 참여하세요!

# 특징

- 실시간 데이터 관찰합니다.
- 실시간 데이터 및/또는 이동 평균을 사용하여 그래프를 만듭니다.
- 매개 변수가 구성된 상태에서 시뮬레이션을 실행합니다.
- 매개 변수가 구성된 사용자 지정 백테스트를 실행합니다.
- 매개 변수가 구성된 라이브 봇을 실행합니다.
- 사용자가 통계를 교환하거나 볼 수 있는 텔레그램 통합.
- 사용자 지정, 이익을 만들거나 손절가를 제한합니다.
- 수익을 창출합니다.
- 내장된 최적화 프로그램을 사용하여 전략을 최적화할 수 있습니다.
- 자신만의 맞춤형 전략을 만들 수 있습니다.

# 사용자 인터페이스

![Main Interface](https://i.imgur.com/Y6FD5O5.png)
![Configuration](https://i.imgur.com/JTvHRXf.png)
![Graphs](https://i.imgur.com/M9Oz3Q6.png)
![News](https://i.imgur.com/Ec6Tw17.png)

# 부인

봇의 사용법은 이와 같습니다. Algobot은 어떠한 재정적 부담이나 예상치 못한 금전적 문제 혹은 결함에 책임이 없습니다.

# 라이선스

GNU General Public License v3.0

# 원작자

Mihir Shrestha

# 기여자

koutsie, Malachi Soord (inverse)

# 특별한 기여자

이 프로젝트 전반에 걸친 전략적 개발의 창시자이자 책임자인 Peter Motin에게 감사드립니다.

# 기여

시작하려면 우리의 [기여 가이드라인](CONTRIBUTING.md)을 확인하세요.

# 기능 요청

모든 기능 요청의 경우에, 깃허브의 이슈를 통해 기능 요청을 자유롭게 추가할 수 있습니다. 우리는 당신의 아이디어를 듣고 애플리케이션에 구현하고 싶습니다.

# 위키

당신은 [여기](https://github.com/ZENALC/algobot/wiki)에서 Algobot에 대한 문서를 찾을 수 있습니다.
