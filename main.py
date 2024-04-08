import os
import xmlrpc.client
import yaml
import re
import base64
import os
import shlex
import subprocess
from github import Github, Auth, InputGitTreeElement
from github.GithubException import GithubException, UnknownObjectException


REPOSITORY = os.getenv("REPOSITORY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPOSITORIES = os.getenv("REPOSITORIES")

PREFIX = "third-party"
DEFAULT_BRANCH = "main"
PR_BRANCH = "auto-main"


# Set the output value by writing to the outputs in the Environment File, mimicking the behavior defined here:
#  https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-an-output-parameter
def set_github_action_output(output_name, output_value):
    f = open(os.path.abspath(os.environ["GITHUB_OUTPUT"]), "a")
    f.write(f"{output_name}={output_value}")
    f.close()


# def main():
#     my_input = os.environ["INPUT_MYINPUT"]
#     my_output = f"Hello {my_input}"
#     set_github_action_output("myOutput", my_output)


def get_last_item(string, sep="/"):
    return string.split(sep)[-1] if sep in string else string


def get_repositories(repo_name):
    def transform(items):
        # {'merges': ['origin 16.0'], 'remotes': {'origin': 'https://github.com/oca/account-analytic.git'}, 'target': 'origin 16.0'}
        name = get_last_item(items[0])
        branch = get_last_item(items[1]["target"], " ")
        url = re.sub("(\/\/\$[a-zA-Z\_:$]*@)", "//", items[1]["remotes"]["origin"])

        return [name, [url, branch]]

    content = yaml.safe_load(REPOSITORIES)

    res = dict(
        filter(lambda item: item[0] != repo_name, map(transform, content.items()))
    )

    return [[key, *values] for key, values in res.items()]
    # return res


def add_submodule(name, url, branch):
    # git submodule add -b master <URL> <PATH> && git commit -a && git push -u origin Production
    _run(f"git submodule add -b {branch} {url} third-party/{name}")


def _run(cmd, **options):
    args = shlex.split(cmd)
    try:
        return subprocess.check_output(args, **options)
    except subprocess.CalledProcessError as e:
        print(e)
    return


def _get_gh():
    auth = Auth.Token(GITHUB_TOKEN)
    return Github(auth=auth)


def get_requirements(repo):
    try:
        content = repo.get_contents("requirements.txt").content
        return base64.b64decode(content).decode("utf-8").split("\n")
    except UnknownObjectException:
        return []


def get_tree(items):
    g = _get_gh()
    res, content = [], ""
    requirements = []

    for name, url, branch_name in repositories:
        org = g.get_organization(url.split("/")[-2])
        url = url.replace(".git", "")
        repo = org.get_repo(name)
        branch = repo.get_branch(branch_name)

        commit = repo.get_git_commit(branch.commit.sha)
        print(f"{name} -> {commit.sha}")

        path = f"{PREFIX}/{name}"
        content += f'[submodule "{name}"]\n\tpath = {path}\n\turl = {url}\n'
        requirements += get_requirements(repo)

        res.append(
            InputGitTreeElement(
                **{
                    "path": path,
                    "mode": "160000",
                    "type": "commit",
                    "sha": commit.sha,
                }
            )
        )

    requirements = set(
        filter(lambda item: item and not item.startswith("#"), requirements)
    )
    print("Requirements: %s" % requirements)
    res.append(
        InputGitTreeElement(
            **{
                "path": "submodules-requirements.txt",
                "mode": "100644",
                "type": "blob",
                "content": "\n".join(requirements),
            }
        ),
    )
    res.insert(
        0,
        InputGitTreeElement(
            **{
                "path": ".gitmodules",
                "mode": "100644",
                "type": "blob",
                "content": content,
            }
        ),
    )

    return res


if __name__ == "__main__":

    org_name, repo_name = REPOSITORY.split("/")

    repositories = get_repositories(repo_name)
    tree = get_tree(repositories)

    g = _get_gh()
    org = g.get_organization(org_name)
    repo = org.get_repo(repo_name)

    # Get or create 'main' branch from default branch
    try:
        branch = repo.get_branch(DEFAULT_BRANCH)
        main_sha = branch.commit.sha
    except GithubException:
        default_branch = repo.get_branch(repo.default_branch)
        sha = default_branch.commit.sha
        res = repo.create_git_ref(f"refs/heads/{DEFAULT_BRANCH}", sha)
        branch = repo.get_branch(DEFAULT_BRANCH)
        main_sha = branch.commit.sha

    # Create branch auto-main
    res = repo.create_git_ref(f"refs/heads/{PR_BRANCH}", main_sha)
    branch = repo.get_branch(PR_BRANCH)
    base_sha = branch.commit.sha
    last_commit = repo.get_git_commit(base_sha)

    # Add submodules
    base_tree = repo.get_git_tree(sha=base_sha)
    new_tree = repo.create_git_tree(base_tree=base_tree, tree=tree)

    # Commit
    commit = repo.create_git_commit(
        message="[ADD] Submodules", tree=new_tree, parents=[last_commit]
    )

    # Update ref
    ref = repo.get_git_ref(f"heads/{PR_BRANCH}")
    ref.edit(sha=commit.sha, force=True)

    # Create PR from 'auto-main' to 'main' branch
    repo.create_pull(
        head=PR_BRANCH,
        base=DEFAULT_BRANCH,
        title="Auto converting repository",
    )

    # Set 'main' as default branch
    # repo.edit(default_branch=DEFAULT_BRANCH)
