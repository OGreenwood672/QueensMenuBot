# Queens' College Cambridge Menu bot

This is a bot that takes [the menu](https://www.queens.cam.ac.uk/life-at-queens/catering/dining-hall/weekly-menu/) and puts it [here](https://www.menu.qjcr.org.uk/queens-menu-bot/api/menu/latest.json) and [here](https://www.instagram.com/queensbutterymenu/)

The code quality is fairly poor and 90% AI so I would reccomend rewriting or just getting AI to do changes rather than actually trying to go through this yourself

use 
```
python3 -m api.publish_cli --once --mode auto
```
to run

use 
```
python3 -m api.index
```
to launch the website which lets you log in and get meta auth tokens