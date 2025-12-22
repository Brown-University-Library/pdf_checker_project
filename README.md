# purpose

This is a template for new django projects -- to standardize on some nice features/practices, and to get up and running, locally, easily and quickly. It provides instructions for getting the template from GitHub, customizing it, starting the webapp, and lists a few things to try with the webapp running. Finally, it lists the nice features/practices, and also shows typical usage.

on this page...
- [local quick-start](#local-quick-start)
- [stuff to try](#stuff-to-try)
- [nice features/practices](#nice-featurespractices)
- [regular setup](#regular-setup)

--- 


# local quick-start

Notes about the quick-start instructions...

- The instructions below assume:
    - a unix-like environment (ie Mac, Linux, or Windows Subsystem for Linux (WSL)). 
    - you've installed `uv` ([link][uv_link])

- The instructions below reference `x_project_stuff`, `x_project`, and `x_app`. In all cases replace with the name of your project, like: `isbn_api_project_stuff`, `isbn_api_project`, and `isbn_api_app`.

- The `update_project_and_app_references.py` script ([link](https://github.com/Brown-University-Library/django_template_52_project/blob/main/update_project_and_app_references.py)) deletes the cloned `.git` directory (in addition to its main purpose to rename the project). Why? So you don't accidentally start building away and commit to the template repo. After this installation, creating a new git repo is one of the first things you should do.

- When you start the webapp via `runserver`, you'll get a message that there are migrations that need to be run, with instructions. You can do that later.

```bash
## setup directories
$ mkdir ./x_project_stuff  # again, replace `x_project_stuff` with your project-stuff directory name
$ cd ./x_project_stuff/
$ mkdir ./logs
$ mkdir ./DBs

## get the project-code
$ git clone https://github.com/Brown-University-Library/django_template_52_project.git

## update project-name (line below is a single long line; clarifying in case it wraps)
$ uv run --python 3.12 ./django_template_52_project/update_project_and_app_references.py --target_dir "./django_template_52_project/" --new_project_name "x_project" --new_app_name "x_app"  # again, replace `x_project` and `x_app` with your project and app names

## setup the envar-settings
$ cd ./x_project/  # again, this will be the project-name you chose
$ cp ./config/dotenv_example_file.txt ../.env

## make the venv
$ uv sync --upgrade

## run the app
$ uv run ./manage.py runserver  # you can ignore the migration-message for now
```

That's it!

---

About the migrations message -- again, you can do that later... Migrations are Django’s system for managing changes to your database schema. When you do run the migrations, do it like this:

```bash
$ cd ./x_project_stuff/x_project/  # again, use your stuff/project names
$ uv run ./manage.py migrate  # calling migrate this way auto-activates the venv
```

[uv_link]: <https://docs.astral.sh/uv/getting-started/installation/>

---


# regular usage

After the above one-time setup, for ongoing development...

```bash
$ cd ./x_project_stuff/x_project  # again, use your stuff/project names
$ uv run ./manage.py runserver  # calling runserver this way auto-activates the venv
```

---


# stuff to try

- Open a browser to <http://127.0.0.1:8000/>. That'll redirect to <http://127.0.0.1:8000/info/>. 

- Try adding `?format=json` to the info url to see the data feeding the the template.

- Try <http://127.0.0.1:8000/error_check/>. You'll see the intentionally-raised error in the browser (would result in a `404` on production), but if you want to confirm that this really would send an email, open another terminal window and type:
    ```bash
    $ uv run --python 3.12 --with aiosmtpd -m aiosmtpd -n -c aiosmtpd.handlers.Debugging --listen localhost:1026
    ```

    This runs an email server in debugging mode so that it'll print, to the console, all received emails, rather than delivering them.    

    You won't initially see anything, but if you reload the error-check url, and then check this terminal window again, you'll see the email-data that would have been sent.

- Try <http://127.0.0.1:8000/version/>. Once you `git init`, `git add --all`, and `git commit -am "initial commit"`, it'll show the branch and commit -- _very_ handy for dev and prod confirmations.

- Try `$ uv run ./manage.py test`. There are two simple tests that should pass.

- Check out the logs (`project_stuff/logs/`). The envar log-level is `DEBUG`, easily changed. On the servers that should be `INFO` or higher, and remember to rotate them, not via python's log-rotate -- but by the server's log-rotate.

Next -- well, the sky's the limit!

---


# nice features/practices

- Nothing private is in the project-repo; avoids using the `.gitignore` for security.
- Shows pattern to keep `views.py` functions short-ish, to act as manager functions (eg `views.version()`).
- Shows pattern to expose the data used by the page via adding `?format=json` (eg `views.info()`). Useful for developing the front-end and troubleshooting.
- Log-formatting shows useful stuff.
- Git branch/commit url is constructed in a way that avoids the new git `dubious ownership` error.
- Includes a couple of client-get tests that respond differentially to dev and prod settings.
- Includes a dev-only error-check url (enables confirmation that email-admins-on-error is set up correctly).
- Uses python-dotenv.
- Uses a `pyproject.toml` file to specify the python version and dependencies.
    - Uses tilde-comparators (`~=`) in the dependency specifications, to the patch-version, for stable upgrades.
    - Uses a `uv.lock` file (created from the `pyproject.toml` file), which the `uv sync` command uses to create and populate the venv.
- Demonstrates how, after the initial `uv sync`, there is no need to activate the venv to run commands.
- Shows one possible pattern to make async calls (`app/lib/version_helper.manage_git_calls()`) and gather together the results.
- This starter webapp doesn't access the db much, but if it did, and you wanted to inspect the sql generated by the ORM, uncomment out the `django.db.backends` logger in `settings.py`.
- Includes a default config-file for [ruff](https://docs.astral.sh/ruff/), a fast, extensible python linter/code-formatter that can integrate with many popular code editors such as VS Code, PyCharm, and others -- or be run from the command line.
- Includes a `run_tests.py` script that runs the tests for this webapp -- compatible with github-ci.
- Includes a `ci_tests.yaml` file for github-ci.

---
