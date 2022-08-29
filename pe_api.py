import requests
import dbqueries
from bs4 import BeautifulSoup
import phone_api

CREDENTIALS_LOCATION = "session_cookies.txt"
BASE_URL = "https://projecteuler.net/minimal={0}"
NOT_MINIMAL_BASE_URL = "https://projecteuler.net/{0}"


def req_to_project_euler(url, login=True):

    with open(CREDENTIALS_LOCATION, "r") as file:
        lines = file.readlines()
    lines[0] = lines[0].replace("\n", "")
    lines[1] = lines[1].replace("\n", "")
    phpSessId, keepAlive = lines
    cookies = {'PHPSESSID': phpSessId, 'keep_alive': keepAlive}

    try:
        r = requests.get(url, cookies=cookies)

        if r.status_code != 200:
            print(r.status_code)
            print(r.text)
            phone_api.bot_crashed(r.status_code)
            return None
        else:
            return r.text

    except Exception as err:
        phone_api.bot_crashed("Runtime Error")
        print(err)
        return None


def keep_session_alive():

    url = BASE_URL.format("friends")
    data = req_to_project_euler(url, True)

    if data is None:
        return None

    all_solved = []

    members = list(map(lambda x: x.split("##"), data.split("\n")))
    db_members = dbqueries.single_req("SELECT * FROM members;")
    names = list(map(lambda x: db_members[x]["username"], db_members))

    connection = dbqueries.open_con()

    people_passed_nothing_changed = 0

    for member in members:

        if len(member) == 1:
            continue

        format_member = list(map(lambda x: x if x != "" else "Undefined", member))
        format_member[4] = (format_member[4] if format_member[4] != "Undefined" else '0')
        format_member[6] = format_member[6].replace("\r", "")

        if format_member[0] in names:
            db_member = db_members[names.index(format_member[0])]
            if str(db_member['solved']) != format_member[4]:

                print("Change on member", format_member[0], "on problems solved")

                previously_solved = db_member["solve_list"]
                currently_solved = format_member[6]

                previously_solved = previously_solved + "0" * (len(currently_solved) - len(previously_solved))

                solved = []

                l = len(currently_solved)
                for i in range(1, l+1):
                    if previously_solved[i - 1] != currently_solved[i - 1]:
                        solved.append(i)

                all_solved.append([format_member[0], solved, db_member['discord_id'], format_member[4]])

                print("{0} solved the problem {1}".format(format_member[0], ",".join(list(map(str, solved)))))

                temp_query = "UPDATE members SET solved={0}, solve_list='{1}' WHERE username = '{2}';"
                temp_query = temp_query.format(format_member[4], format_member[6], format_member[0])
                dbqueries.query(temp_query, connection)

            else:
                people_passed_nothing_changed += 1
        else:

            awards = get_awards(format_member[0])

            temp_query = "INSERT INTO members (username, nickname, country, language, solved, solve_list, discord_id, awards, awards_list) VALUES ('{0}', '{1}', '{2}', '{3}', {4}, '{5}', '', {6}, '{7}')"
            temp_query = temp_query.format(format_member[0], format_member[1], format_member[2], format_member[3], format_member[4], format_member[6], awards[0], awards[1])
            dbqueries.query(temp_query, connection)
            print("Added", format_member[0])

    print("End of check, passed {0} people".format(people_passed_nothing_changed))

    dbqueries.close_con(connection)
    return all_solved


def problem_def(n):
    data = req_to_project_euler(BASE_URL.format("problems"))
    lines = data.split("\n")
    pb = lines[n].replace("\r", "")
    specs = pb.split("##")
    return specs


def last_problem():
    data = req_to_project_euler(BASE_URL.format("problems"))
    return len(data.split("\n")) - 2


def get_kudos(username):

    url = NOT_MINIMAL_BASE_URL.format("progress={0};show=posts".format(username))
    data = req_to_project_euler(url)
    soup = BeautifulSoup(data, 'html.parser')
    div = soup.find(id='posts_made_section')

    post_made, kudos_earned = div.find_all("h3")[0].text.split(" / ")
    post_made = int(post_made.split(" ")[2])
    kudos_earned = int(kudos_earned.split(" ")[2])

    posts = [list(map(lambda x: int(x.text), post.find_all("span"))) for post in div.find_all(class_="post_made_box")]
    return [post_made, kudos_earned, posts]


def update_kudos(username):

    posts_made, kudos_earned, posts_list = get_kudos(username)

    connection = dbqueries.open_con()
    temp_query = "SELECT * FROM pe_posts WHERE username = '{0}';".format(username)
    data = dbqueries.query(temp_query, connection)

    posts_txt = "|".join(["n".join(map(str, p)) for p in posts_list])

    changes = []
    total_change = 0

    if len(data.keys()) == 0:
        temp_query = "INSERT INTO pe_posts (username, posts_number, kudos, posts_list) VALUES ('{0}', {1}, {2}, '{3}');".format(username, posts_made, kudos_earned, posts_txt)
        dbqueries.query(temp_query, connection)
    else:
        previous = data[0]
        previous_posts = list(map(lambda x: list(map(int, x.split("n"))), previous["posts_list"].split("|")))
        if previous["kudos"] != kudos_earned:
            total_change = kudos_earned - previous["kudos"]
            for post in posts_list:
                for previous_post in previous_posts:
                    if post[0] == previous_post[0]:
                        if post[1] != previous_post[1]:
                            changes.append([post[0], post[1] - previous_post[1]])
                        break
        if previous["posts_number"] != posts_made or previous["kudos"] != kudos_earned:
            temp_query = "UPDATE pe_posts SET posts_number='{0}', kudos='{1}', posts_list='{2}' WHERE username='{3}'".format(posts_made, kudos_earned, posts_txt, username)
            dbqueries.query(temp_query, connection)

    dbqueries.close_con(connection)
    return [kudos_earned, total_change, changes]


def is_discord_linked(discord_id, connection=None):

    if connection is None:
        data = dbqueries.single_req("SELECT * FROM members WHERE discord_id='{0}';".format(discord_id))
    else:
        data = dbqueries.query("SELECT * FROM members WHERE discord_id='{0}';".format(discord_id), connection)
    return len(data.keys()) == 1


def unsolved_problems(username):

    url = BASE_URL.format("friends")
    data = req_to_project_euler(url, True)
    if data is None:
        pass

    members = list(map(lambda x: x.split("##"), data.split("\n")))

    usernames = list(map(lambda x: x[0], members))
    if username not in usernames:
        return None

    member_solves = members[usernames.index(username)][6]

    data = req_to_project_euler(BASE_URL.format("problems"))
    problems = list(map(lambda x: x.replace("\r", ""), data.split("\n")))

    unsolved = []

    for index, solved in enumerate(list(member_solves)):
        if solved == "0":
            unsolved.append(problems[index + 1].split("##"))

    unsolved = sorted(unsolved, key=lambda x: int(x[3]), reverse=True)
    return unsolved


def get_awards(username):

    url = NOT_MINIMAL_BASE_URL.format("progress={0};show=awards".format(username))
    data = req_to_project_euler(url)
    soup = BeautifulSoup(data, 'html.parser')

    div1 = soup.find(id="problem_solving_awards_section")
    div2 = soup.find(id="forum_based_awards_section")

    problem_awards = div1.find_all(class_="award_box")
    solves_problem = [1 if len(problem.find_all(class_="smaller green strong")) == 1 else 0 for problem in problem_awards]

    forum_awards = div2.find_all(class_="award_box")
    solves_forum = [1 if len(problem.find_all(class_="smaller green strong")) == 1 else 0 for problem in forum_awards]

    return [sum(solves_problem) + sum(solves_forum), "".join(list(map(str, solves_problem)))+"|"+"".join(list(map(str, solves_forum)))]


def update_awards(username):

    connection = dbqueries.open_con()
    temp_query = "SELECT username, awards, awards_list FROM members WHERE username='{0}';".format(username)
    data = dbqueries.query(temp_query, connection)[0]

    current_data = get_awards(username)

    changes = []

    first_len = len(current_data[1].split("|")[0])
    second_len = len(current_data[1].split("|")[1])

    if data["awards_list"] != current_data[1]:
        for i in range(first_len):
            if current_data[1][i] == "1" and data["awards_list"][i] == "0":
                changes.append(i)
        for j in range(first_len + 1, first_len + 1 + second_len):
            if current_data[1][j] == "1" and data["awards_list"][j] == "0":
                changes.append(j-1)

    temp_query = "UPDATE members SET awards={0}, awards_list='{1}' WHERE username='{2}';".format(current_data[0], current_data[1], username)
    dbqueries.query(temp_query, connection)
    dbqueries.close_con(connection)

    return [current_data[0], changes]


def all_members_in_database():
    data = dbqueries.single_req("SELECT username FROM members;")
    return list(map(lambda x: x["username"], [data[k] for k in data.keys()]))


def get_awards_specs():
    url = NOT_MINIMAL_BASE_URL.format("progress;show=awards")
    data = req_to_project_euler(url)
    soup = BeautifulSoup(data, 'html.parser')

    all_awards = []

    d_problems = soup.find(id="problem_solving_awards_section").find_all(class_="tooltip inner_box")
    all_awards.append([problem.find_all(class_="strong")[0].text for problem in d_problems])

    d_problems = soup.find(id="forum_based_awards_section").find_all(class_="tooltip inner_box")
    all_awards.append([problem.find_all(class_="strong")[0].text for problem in d_problems])

    return all_awards


if __name__ == "__main__":
    get_awards_specs()
