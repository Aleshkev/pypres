import argparse
import dataclasses
import getpass
import itertools
import logging
import os
import pathlib
import re
from typing import *

import bs4
import humanize
import jinja2
import requests
import slugify
import yaml

log = logging.getLogger('pyprez')
logging.basicConfig(level=logging.INFO)


@dataclasses.dataclass
class BestSubmission:  # The submission used in the ranking, usually 'last', not 'best'.
    task_id: str = ""
    points: int = 0
    table_html: str = ""  # The HTML of the table, ripped alive from SIO2.
    code_html: str = ""  # The HTML of highlighted code of the submission.


@dataclasses.dataclass
class UserSubmissions:
    name: str
    submissions: List[BestSubmission] = dataclasses.field(default_factory=list)

    @property
    def last_name(self):
        return self.name.split()[-1]  # Not internationally correct, but will do for now.


StrGen = Callable[[], str]


class SIO2Session:
    def __init__(self, ranking_url: str, username: Optional[str] = None, password: Optional[StrGen] = None,
                 cache: pathlib.Path = pathlib.Path('cache/'), clear_cache: bool = False):
        self.ranking_url = ranking_url
        self.host, = re.findall(r'https://[a-zA-Z0-9.]+', ranking_url)
        self.cache = cache

        if not self.cache.is_dir():
            os.makedirs(str(self.cache), exist_ok=True)

        if clear_cache:
            log.info(f"Clearing cache: {self.cache}")
            for f in self.cache.glob("*"):
                f.unlink()

        self.session = requests.Session()
        self._logged_in = False
        if username:
            assert password
            self._login(username, password)
        self._css_url = None
        self._syntax_style = None

    def _get_url(self, url: str, *, fresh: bool = False, no_login: bool = False):
        cache_file = self.cache / slugify.slugify(f"{url}")
        if cache_file.is_file() and not fresh:
            log.info(f"File from cache: {url} → {cache_file.name}")
            return cache_file.read_text(encoding="utf-8")
        else:
            log.info(f"Saving to cache: {url} → {cache_file.name}")
            assert no_login or self._logged_in, "Session must be logged in to access uncached urls."
            text = self.session.get(url).text
            cache_file.write_text(text, encoding="utf-8")
            return text

    def _get_soup(self, url: str, *, fresh: bool = False, no_login: bool = False):
        return bs4.BeautifulSoup(self._get_url(url, fresh=fresh, no_login=no_login), "html.parser")

    def _random_contest_url(self):
        log.info(f"Searching for any contest: {self.host}")
        for a in self._get_soup(self.host, no_login=True).find_all("a"):
            if re.match(r"/c/.*/", a.get("href")):
                return self.host + a.get("href")

    def _login(self, username: str, password: StrGen):
        login_url = f"{self._random_contest_url()}login/"
        log.info(f"Forging referer: {login_url}")
        self.session.get(login_url)
        log.info(f"Requesting login: {login_url}")
        self.session.post(login_url,
                          data={"csrfmiddlewaretoken": self.session.cookies["csrftoken"], "username": username,
                                "password": password()}, headers={"Referer": login_url})

        self._logged_in = True
        displayed = self._get_soup(self.host, fresh=True).find(id="navbar-username").text.strip()
        assert displayed == username, "Login failed."

    def get_user_submissions(self):
        user_submissions: List[UserSubmissions] = []

        ranking_page = self._get_soup(self.ranking_url)
        header_tr, *ranking_trs = ranking_page.find_all("tr")
        _, _, *task_ids, _ = map(lambda x: x.text, header_tr.find_all("th"))

        css_link, _ = filter(lambda x: x.get("href").endswith(".css"), ranking_page.find_all("link"))
        self._css_url = css_link.get("href")

        for ranking_tr in ranking_trs:
            _, name_td, *score_tds, _ = ranking_tr.find_all("td")
            name = name_td.text
            user_submissions.append(UserSubmissions(name))

            for task_id, score_td in zip(task_ids, score_tds):
                if not score_td.text:
                    continue
                score = int(score_td.text)
                submission_url = self.host + score_td.find("a").get("href")

                submission_page = self._get_soup(submission_url)
                table_table, *_ = filter(lambda x: "submission" in x.get("class"), submission_page.find_all("table"))
                for i in itertools.chain(*(table_table.find_all(x) for x in ("script", "div", "span"))):
                    i.extract()

                source_page = self._get_soup(submission_url + "source/")
                source_div, = source_page.find_all("div", class_="syntax-highlight")

                if not self._syntax_style:
                    self._syntax_style, = source_page.find_all("style")
                    self._syntax_style = str(self._syntax_style)

                user_submissions[-1].submissions.append(BestSubmission(task_id, score,
                                                                       table_table.prettify(),
                                                                       source_div.prettify()))
        user_submissions.sort(key=lambda x: x.last_name)
        return user_submissions

    def get_css(self):
        assert self._css_url and self._syntax_style, "CSS link was not generated yet, use get_user_submissions() first."
        return self._get_url(self.host + self._css_url, no_login=True), self._syntax_style


def make_presentation(config: pathlib.Path, cache: pathlib.Path, clear_cache: bool = False,
                      login: Optional[str] = None, password: Optional[StrGen] = None):
    config = yaml.load(config.read_text(encoding="utf-8"))

    session = SIO2Session(config["ranking_url"], login, password, cache=cache, clear_cache=clear_cache)
    user_submissions = session.get_user_submissions()
    copied_css, syntax_style = session.get_css()

    env = jinja2.Environment(loader=jinja2.PackageLoader(__name__, '.'), autoescape=False)
    template = env.get_template("template.html")

    props = {
        "lang": config.get("lang", "pl"),
        "contest_name": config.get("contest_name", "contest_name"),
        "credits": config.get("credits"),
        "preamble": config.get("preamble"),
        "copied_css": copied_css,
        "syntax_style": syntax_style,
        "font": config.get("font", "Georgia, sans-serif"),
        "user_submissions": user_submissions
    }

    return template.render(props)


def command_line():
    parser = argparse.ArgumentParser(description="Create a presentation.")
    parser.add_argument("--config", "-c", metavar="CONFIG-FILE", type=str, default="config.yaml",
                        help="Path to YAML configuration file. Defaults to ./config.yaml")
    parser.add_argument("--login", "-l", type=str, default=None,
                        help="(Moderator's) login to SIO2. "
                             "If not given, the script will attempt to run without logging in, "
                             "what usually crashes the program.")
    parser.add_argument("--password", "-p", type=str, default=None,
                        help="Path to file with the password. "
                             "If not given but --login is used, the script will ask.")
    parser.add_argument("--fresh", "-f", action="store_true",
                        help="Clear cache. You have to enable it if you want to refresh the data in the presentation.")
    parser.add_argument("--cache", metavar="CACHE-DIR", type=str, default="cache/",
                        help="Path where the cache files will be stored. Defaults to ./cache/")
    parser.add_argument("--output", "-o", type=str, default="presentation.html",
                        help="Where the resulting presentation will be saved. "
                             "Defaults to ./presentation.html")
    args = parser.parse_args()

    config_file = pathlib.Path(args.config)
    log.info(f"Using config: {config_file}")
    assert config_file.is_file() and config_file.suffix == '.yaml'
    login, password = args.login, args.password
    if login:
        log.info(f"Using login: {login}")
        if not password:
            log.info(f"Will ask for password.")
            password_gen = lambda: getpass.getpass(prompt=f"Password for {login}: ")
        else:
            password = pathlib.Path(password)
            log.info(f"Will load password: {password}")
            password_gen = lambda: password.read_text(encoding="utf-8")
    else:
        assert not password, "--password requires --login"
        log.info(f"Won't log in, meaning any uncached resources won't be accessible and will crash the script.")
        password_gen = None
    fresh = args.fresh
    cache_dir = pathlib.Path(args.cache)
    if fresh:
        log.info(f"Will reset cache.")
        assert login, "--fresh always requires --login"

    log.info(f"Generating presentation...")
    presentation = make_presentation(config_file, cache_dir, fresh, login, password_gen)

    log.info(f"Saving to file.")
    output_file = pathlib.Path(args.output)
    output_file.write_text(presentation, encoding="utf-8")
    print(f"Saved presentation to {output_file} ({humanize.naturalsize(os.path.getsize(output_file))}).")


if __name__ == "__main__":
    command_line()
