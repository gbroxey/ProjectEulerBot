import requests
from bs4 import BeautifulSoup

import datetime
import pytz
import json
import time

# import dbqueries
import pe_database

import phone_api

from rich.console import Console
from rich import inspect

from typing import List, Dict, Optional, Any, Tuple


TOTAL_REQUESTS = 0
TOTAL_SUCCESS_REQUESTS = 0
SESSION_REQUESTS = 0
LAST_REQUEST_SUCCESSFUL = False
LAST_REQUEST_TIME = datetime.datetime.now(pytz.utc)


CREDENTIALS_LOCATION = "session_cookies.txt"
BASE_URL = "https://projecteuler.net/minimal={0}"
NOT_MINIMAL_BASE_URL = "https://projecteuler.net/{0}"

COOKIES = {}

console = Console()


def pe_api_setup(cookies, account) -> None:

    global COOKIES
    COOKIES = cookies

    account_name = account["username"]

    console.log(f"[-] Added credential for account {account_name}")



class ProjectEulerRequest:


    @staticmethod
    def request_failed() -> None:
        """
        When called, increase a global variable, counting how many requests failed.
        """
        global LAST_REQUEST_SUCCESSFUL
        LAST_REQUEST_SUCCESSFUL = False


    @staticmethod
    def request_succeeded() -> None:
        """
        When called, increase a global variable, counting how many requests succeeded.
        """
        global LAST_REQUEST_SUCCESSFUL, LAST_REQUEST_TIME, TOTAL_SUCCESS_REQUESTS
        
        LAST_REQUEST_SUCCESSFUL = True
        LAST_REQUEST_TIME = datetime.datetime.now(pytz.utc)
        TOTAL_SUCCESS_REQUESTS += 1

    
    def __init__(self, target_url: str, need_login: bool = True) -> None:

        global TOTAL_REQUESTS, SESSION_REQUESTS
        
        TOTAL_REQUESTS += 1
        SESSION_REQUESTS += 1

        if need_login:
            cookies = COOKIES
        else:
            cookies = {}

        try:
            # Do the request to the website, with the right cookies that emulate the account
            r = requests.get(target_url, cookies=cookies)
            self.status = int(r.status_code)
            
            if r.status_code != 200:
                # Phone API is sending a notifications to teyzer's phone
                phone_api.bot_crashed(r.status_code)
                ProjectEulerRequest.request_failed()
                self.response: str | Exception | None = None
                console.log(r.text)
            else:
                ProjectEulerRequest.request_succeeded()
                self.response: str | Exception | None = r.text

        except Exception as err:
            phone_api.bot_crashed("Runtime Error")
            ProjectEulerRequest.request_failed()
            self.status = None
            self.response: str | Exception | None = err
        




        

class PE_Problem:
    
    def __init__(self, problem_id: int, name: str = None, unix_publication: int = None, solves: int = None, 
                 solves_in_discord: int = None, difficulty_rating: int = None):
        self.name = name
        self.problem_id = problem_id
        self.unix_publication = unix_publication
        self.solves = solves
        self.solves_in_discord = solves_in_discord
        self.difficulty_rating = difficulty_rating
        
    def __str__(self) -> str:
        return str([self.problem_id, self.name, self.unix_publication, self.solves, self.solves_in_discord, self.difficulty_rating])
    
    def __repr__(self) -> str:
        return self.__str__()

    @staticmethod
    def complete_list() -> list:

        """
        Returns a list containing all problems. L[i - 1] is thus problem i. Each
        element is a PE_Problem instance.
        """

        res_list = []
        
        api_data = ProjectEulerRequest("https://projecteuler.net/minimal=problems", False)
        
        rows = api_data.response.split("\n")
        timestamps = [int(x.split("##")[2]) for x in rows[1:-1]]
        
        ux_data = ProjectEulerRequest("https://projecteuler.net/progress", True)
        soup = BeautifulSoup(ux_data.response, 'html.parser')
        div = soup.find_all("span", class_='tooltiptext_narrow')
        
        for element in div:
            
            properties = list(map(
                lambda x: x.text, 
                element.find_all("div")
            ))
            
            if len(properties) == 0:
                continue
            
            problem_id = int(properties[0].split()[1])
            solvers = int(properties[1].split()[2])
            
            if len(properties) == 3:    
                difficulty = None
                title = properties[2].replace("\"", "")
            elif len(properties) == 4:
                difficulty = int(properties[2].split(": ")[1].split("%")[0])
                title = properties[3].replace("\"", "")
            else:
                raise Exception("Properties did not have 3 or 4 fields, resulted in title not being defined")
            
            pb = PE_Problem(problem_id, name=title, unix_publication=timestamps[problem_id - 1], solves=solvers, difficulty_rating=difficulty)
            res_list.append(pb)
                
        return res_list
        

class Member:
    
    
    def __init__(self, _username: str = None, _nickname: str = None, _country: str = None, _language: str = None,
                 _solve_count: int = None, _level: int = None, _solve_array: list = None, _discord_id: str = None, 
                 _kudo_count: int = None, _kudo_array: list = None, _database_solve_count: int = None, _database_solve_array: List[bool] = None,
                 _award_count: int = None, _award_array: tuple = None, _database_award_count: int = None,
                 _database_award_array: tuple = None, _database_kudo_count: int = None, _database_kudo_array: list = None,
                 _private: bool = None) -> None:
        
        self._username = _username
        self._nickname = _nickname
        self._country = _country
        self._language = _language
        self._level = _level
        
        self._discord_id = None if _discord_id is None else str(_discord_id)
        
        self._pe_solve_count = _solve_count
        self._pe_solve_array = _solve_array
        self._pe_award_count = _award_count
        self._pe_award_array: Tuple[List[bool], List[bool], List[bool]] | None = _award_array
        self._pe_kudo_count = _kudo_count
        self._pe_kudo_array: List[Tuple[int, int]] = _kudo_array
        
        self._database_solve_count = _database_solve_count
        self._database_solve_array = _database_solve_array
        self._database_award_count = _database_award_count
        self._database_award_array: Tuple[List[bool], List[bool], List[bool]] | None = _database_award_array
        self._database_kudo_count = _database_kudo_count
        self._database_kudo_array: List[Tuple[int, int]] = _database_kudo_array
        
        self._private = _private
        
    
    def __str__(self) -> str:
        return f"{self._username}/{self._discord_id}/{self._pe_solve_count}/{self._database_solve_count}"
        

    def __repr__(self) -> str:
        return self.__str__()

        
    def update_from_friend_list(self, friend_page: Optional[ProjectEulerRequest] = None) -> None:

        """
        Update the Member object according to the bot's friend list.

        You can pass the data of the friends page if you already have the data
        and don't want to reload it.
        """

        if friend_page is None:
            friend_page = ProjectEulerRequest(BASE_URL.format("friends"))
        
        if friend_page.status != 200:
            ProjectEulerRequest.request_failed()
            raise Exception("Request failed")

        # This is because ## is used as separator in https://projecteuler.net/minimal=friends, and thus C# and F# are an issue
        format_func = lambda x: x.replace("C###", "Csharp##").replace("F###", "Fsharp##").split("##")
        text_response = list(map(format_func, friend_page.response.split("\n")))
        
        target_member = None
        for element in text_response:
            if element[0] == self.username():
                target_member = element
                break

        if target_member is None:
            raise Exception("Member not found in friend list")
        
        undef_func = lambda x, int_type: \
            (0 if int_type else "Undefined") if x == "" else (int(x) if int_type else x)
        
        self._nickname = undef_func(target_member[1], False)
        self._country = undef_func(target_member[2], False)
        self._language = undef_func(target_member[3], False)
        self._pe_solve_count = undef_func(target_member[4], True)
        self._level = undef_func(target_member[5], True)
        self._pe_solve_array = [
            c == "1" for c in 
            filter(lambda x: x in "01", target_member[6])
        ]

    
    def update_from_award_list(self) -> None:

        """
        Update the awards of the member according to their awards page.
        """
        
        request_url = NOT_MINIMAL_BASE_URL.format(f"progress={self.username()};show=awards")
        kudo_page = ProjectEulerRequest(request_url)
        
        if kudo_page.status != 200:
            ProjectEulerRequest.request_failed()
            raise Exception("Request failed")
        
        soup = BeautifulSoup(kudo_page.response, 'html.parser')

        awards_container = soup.find(id="awards_section").find_all("div", recursive=False)

        div1 = awards_container[0]
        div2 = awards_container[1]
        div3 = awards_container[2]

        problem_awards = div1.find_all(class_="award_box")
        solves_problem = [1 if len(problem.find_all(class_="smaller green strong")) == 1 else 0 for problem in problem_awards]

        problem_publication = div2.find_all(class_="award_box")
        solves_publication = [1 if len(problem.find_all(class_="smaller green strong")) == 1 else 0 for problem in problem_publication]
        
        forum_awards = div3.find_all(class_="award_box")
        solves_forum = [1 if len(problem.find_all(class_="smaller green strong")) == 1 else 0 for problem in forum_awards]

        self._pe_award_count = sum(solves_problem) + sum(solves_publication) + sum(solves_forum)
        self._pe_award_array = tuple(map(
            lambda x: [str(c) == "1" for c in x],
            [solves_problem, solves_publication, solves_forum]
        ))
        
        
    def update_from_post_page(self) -> None:

        """
        Update the Member's posts according to their post page.
        """

        request_url = NOT_MINIMAL_BASE_URL.format(f"progress={self.username()};show=posts")
        post_page = ProjectEulerRequest(request_url)
        
        if post_page.status != 200:
            ProjectEulerRequest.request_failed()
            raise Exception("Request failed")

        soup = BeautifulSoup(post_page.response, 'html.parser')
        div = soup.find(id='posts_made_section')

        post_made, kudos_earned = div.find_all("h3")[0].text.split(" / ")
        post_made = int(post_made.split(" ")[2])
        kudos_earned = int(kudos_earned.split(" ")[2])

        posts = list(map(
            lambda post: tuple(map(
                lambda x: int(x.text), 
                post.find_all("span")
            )), div.find_all(class_="post_made_box")
        ))
        
        self._pe_kudo_count = sum(list(map(lambda x: x[1], posts)))
        self._pe_kudo_array = posts

    
    
    def update_from_database(self, connection = None, data = None) -> None:

        """
        Downloads all the data from the database regarding this member, and updates all of its properties, so that they can be then used.
        """

        key_id, value_id = self.identity()
        
        def check_function(data_checked: Optional[List]) -> int:

            """
            This function is defined for what happens after.
            If the member we are looking for is within the data, we return 1 but
            in any other case we return 0
            """

            # If the data is None, obviously, we want to retry
            if data_checked is None:
                return 0
            
            # But if the member is within the database's data, we return 1
            for member in data_checked:
                if member[key_id] == str(value_id):
                    return 1
            
            return 0


        while check_function(data) == 0:
            
            if data is not None:
                self.update_from_friend_list()
                self.push_basics_to_database()
            
            temp_query = "SELECT * FROM members;"
            data = pe_database.query_option(temp_query, connection)


        for element in data:

            if element[key_id] == value_id:
                
                self._username = element["username"]
                self._discord_id = str(element["discord_id"])
                self._nickname = element["nickname"]
                self._country = element["country"]
                self._language = element["language"]
                self._database_solve_count = int(element["solved"])
                self._database_solve_array = [c == "1" for c in element["solve_list"]]
                self._database_award_count = element["awards"]
                self._database_award_array = tuple(map(
                    lambda x: [str(c) == "1" for c in x],
                    element["awards_list"].split("|")
                ))
                self._private = (element["private"] == 1)
                break
                
    
    def update_from_database_kudo(self, connection = None, data = None) -> None:
        
        key_id, value_id = self.identity()

        def check_function(data_checked: Optional[List]) -> int:

            """
            Returns 0 if the data does not seem correct, and anything
            but 0 if there is no apparent trouble
            """

            if data_checked is None:
                return 0
            return len(data_checked)

        
        while check_function(data) == 0:
            
            if data is not None:
                self.update_from_post_page()
                self.push_kudo_to_database()
        
            temp_query = f"SELECT * FROM members \
                INNER JOIN pe_posts ON members.username = pe_posts.username \
                WHERE members.{key_id} = '{value_id}'"
            data = pe_database.query_option(temp_query, connection)

    
        for element in data:

            if element[key_id] == value_id:
                
                self._database_kudo_count = int(element["kudos"])
                self._database_kudo_array = list(map(
                    lambda el: tuple(map(
                        int, el.split("n")
                    )), element["posts_list"].split("|")
                ))
                break
        
    
    def identity(self) -> Tuple[str, str]:

        """
        Returns a list of two elements, a key, and a value.
        It allows to check for the identity of the member with member[key] == value. (For a database's row)

        Note that this is needed because a member can have an identity coming from discord
        or from the project euler website, depending on where we have initiated the object.
        """

        if self._username is not None:
            return "username", self.username()
        elif self._discord_id is not None:
            return "discord_id", self.discord_id()
        else:
            raise Exception("Need either a username or a Discord ID")
        

    def private(self) -> bool:
        """
        Returns whether the user wants its username displayed somewhere or not.
        """
        if self._private is None:
            self.update_from_database()
        return self._private
    

    def push_privacy_to_database(self, new_privacy: bool, connection = None) -> None:

        """
        Updates a member's privacy in the database. `new_privacy` set as `true` indicates the member will be private.
        """

        new_value = "1" if (new_privacy == True) else "0"
        dis_id = self.discord_id()
        temp_query = f"UPDATE members SET private = {new_value} WHERE discord_id = '{dis_id}';"

        pe_database.query_option(temp_query, connection)
        self._private = new_privacy


    def username(self) -> str:
        """
        Returns the Project Euler username of the member.
        """
        if self._username is None:
            self.update_from_database()
        return self._username
    

    def username_option(self) -> str:
        """
        Returns the Project Euler username or "Private Account" if the account is private
        """
        if self.private():
            return "Private Account"
        return self.username()
    

    def nickname(self) -> str:
        """
        Returns the nickname of the account on Project Euler. This can be an empty string.
        """
        if self._nickname is None:
            self.update_from_database()
        return self._nickname
    

    def username_ping(self) -> str:

        """
        Returns the username formatted for discord code blocks, along with the discord ping if available
        """

        dis_id = self.discord_id()

        if self.private():
            return f"`Private Profile`"

        if dis_id != "":
            return f"`{self.username()}` (<@{dis_id}>)"
        
        return f"`{self.username()}`"  
    

    def country(self) -> str:
        """
        Returns the country of the Project Euler account
        """
        if self._country is None:
            self.update_from_database()
        return self._country
    

    def language(self) -> str:
        """
        Returns the language of the Project Euler account.
        """
        if self._language is None:
            self.update_from_database()
        return self._language
    

    def solve_count(self) -> int:

        """
        Returns the number of solves made by the member.
        """

        if self._pe_solve_count is not None:
            return self._pe_solve_count
        elif self._database_solve_count is not None:
            return self._database_solve_count
        
        self.update_from_database()
        return self._database_solve_count
    

    def pe_solve_count(self) -> int:

        """
        Returns the number of solves made by the member, as seen on Project Euler.
        """

        if self._pe_solve_count is not None:
            return self._pe_solve_count
        
        self.update_from_friend_list()
        if self._pe_solve_count is None:
            raise ValueError("_pe_solve_count should not be None after an update from friend list.")

        return self._pe_solve_count
        

    def database_solve_count(self) -> int:

        """
        Returns the number of solves made by the member in the database.
        This can be different from the number of solves on Project Euler during databases update.
        """

        if self._database_solve_count is not None:
            return self._database_solve_count
        
        self.update_from_database()
        if self._database_solve_count is None:
            raise ValueError("_database_solve_count should not be None after an update from database.")

        return self._database_solve_count
    

    def solve_array(self) -> List[bool]:

        """
        Returns an array of boolean: [b_1, ..., b_last_problem] where every True represents a problem solved
        """

        if self._pe_solve_array is not None:
            return self._pe_solve_array
        elif self._database_solve_array is not None:
            return self._database_solve_array
        
        self.update_from_database()
        if self._database_solve_array is None:
            raise ValueError("_database_solve_array should not be None after update from database.")

        return self._database_solve_array
    

    def pe_solve_array(self) -> List[bool]:

        """
        Returns an array of boolean: [b_1, ..., b_last_problem] where every True represents a problem solved,
        according to Project Euler's values.
        """

        if self._pe_solve_array is not None:
            return self._pe_solve_array
        
        self.update_from_friend_list()
        if self._pe_solve_array is None:
            raise ValueError("_pe_solve_array should not be None after update from friend list.")

        return self._pe_solve_array


    def database_solve_array(self) -> List[bool]:

        """
        Returns an array of boolean: [b_1, ..., b_last_problem] where every True represents a problem solved,
        according to the database's values.
        """
        
        if self._database_solve_array is not None:
            return self._database_solve_array
        
        self.update_from_database()
        if self._database_solve_array is None:
            raise ValueError("_database_solve_array should not be None after update from database.")

        return self._database_solve_array
    

    def has_solved(self, problem: int) -> bool:

        """
        With a problem id, returns whether the member has solved this problem or not.
        """

        if problem - 1 >= len(self.solve_array()):
            return False

        return self.solve_array()[problem - 1]
    

    def award_count(self) -> int:

        """
        Returns the number of awards, classic ones and forum post ones
        """

        if self._pe_award_count is not None:
            return self._pe_award_count
        elif self._database_award_count is not None:
            return self._database_award_count
        
        self.update_from_database()
        return self._database_award_count
    

    def pe_award_count(self) -> int:

        """
        Returns the number of awards according to Project Euler.
        """

        if self._pe_award_count is not None:
            return self._pe_award_count
        
        self.update_from_award_list()
        if self._pe_award_count is None:
            raise ValueError("_pe_award_count should not be None after update from award list.")

        return self._pe_award_count
    

    def database_award_count(self) -> int:

        """
        Returns the number of awards according to the Database.
        """

        if self._database_award_count is not None:
            return self._database_award_count
        
        self.update_from_database()
        if self._database_award_count is None:
            raise ValueError("_database_award_count should not be None after update from database.")

        return self._database_award_count
        

    def award_array(self) -> Tuple[List[bool], List[bool], List[bool]]:

        """
        Returns an array with the awards, like
        ([True, False, ...], [True, False], [True, False, ...])
        Where each boolean represents if the award has been obtained
        
        First array is for main awards and second for forum awards
        Use pe_api.get_awards_specs to get the names of the awards
        """

        if self._pe_award_array is not None:
            return self._pe_award_array
        elif self._database_award_array is not None:
            return self._database_award_array
        
        self.update_from_database()
        return self._database_award_array
    
    
    def pe_award_array(self) -> Tuple[List[bool], List[bool], List[bool]]:
        
        if self._pe_award_array is not None:
            return self._pe_award_array
        
        self.update_from_award_list()
        if self._pe_award_array is None:
            raise ValueError("_pe_award_array should not be None after update from award list.")

        return self._pe_award_array
    
    
    def database_award_array(self) -> Tuple[List[bool], List[bool], List[bool]]:
        
        if self._database_award_array is not None:
            return self._database_award_array
        
        self.update_from_database()
        if self._database_award_array is None:
            raise ValueError("_database_award_array should not be None after update from award list.")

        return self._database_award_array
    
    
    def kudo_count(self) -> int:

        """
        Return the total kudo count
        """

        if self._pe_kudo_count is not None:
            return self._pe_kudo_count
        elif self._database_kudo_count is not None:
            return self._database_kudo_count
        
        self.update_from_post_page()
        return self._database_kudo_count
        
        
    def pe_kudo_count(self) -> int:

        """
        Returns the number of kudo that this user has.
        """
        
        if self._pe_kudo_count is not None:
            return self._pe_kudo_count
        
        self.update_from_post_page()
        if self._pe_kudo_count is None:
            raise ValueError("_pe_kudo_count should not be None after update from post page.")

        return self._pe_kudo_count
    
    
    def database_kudo_count(self) -> int:

        """
        Returns the number of kudo that this user has according to the database.
        """

        if self._database_kudo_count is not None:
            return self._database_kudo_count
        
        self.update_from_database_kudo()
        if self._database_kudo_count is None:
            raise ValueError("_database_kudo_count should not be None after update from kudo database.")

        return self._database_kudo_count
    
    
    def kudo_array(self) -> List[Tuple[int, int]]:

        """
        The list of kudos, in an array like [(107, 5), (108, 2)]
        If the user has 5 kudos for their post on 107 and 2 for 108
        """

        if self._pe_kudo_array is not None:
            return self._pe_kudo_array
        elif self._database_kudo_array is not None:
            return self._database_kudo_array
        
        self.update_from_database_kudo()
        return self._database_kudo_array
        

    def pe_kudo_array(self) -> List[Tuple[int, int]]:
        
        if self._pe_kudo_array is not None:
            return self._pe_kudo_array
        
        self.update_from_post_page()
        if self._pe_kudo_array is None:
            raise ValueError("_pe_kudo_array should not be None after update from post page.")

        return self._pe_kudo_array
    

    def database_kudo_array(self) -> List[Tuple[int, int]]:
        
        if self._database_kudo_array is not None:
            return self._database_kudo_array
        
        self.update_from_database_kudo()
        if self._database_kudo_array is None:
            raise ValueError("_database_kudo_array should not be None after update from kudo database.")

        return self._database_kudo_array
        

    def level(self) -> int:
        """
        Returns the level of the member. This is only `number_of_solves // 25`.
        """
        if self._level is None:
            self.update_from_database()
        return self._level
            

    def discord_id(self) -> str:
        """
        Returns the discord ID of the member. It might be an empty string if not self.is_discord_linked()
        """
        if self._discord_id is None:
            self.update_from_database()
        return self._discord_id
    

    def position_in_discord(self) -> tuple[int, int]:

        """
        Returns the position in the discord (ranking by solve count)
        and the number of member in the discord
        """

        current_rank = 1
        all_members = Member.members_database()
        valid_members = 0

        if not self.is_discord_linked():
            return -1, -1

        member: Member
        for member in all_members:

            if not member.is_discord_linked():
                continue
            valid_members += 1

            if member.solve_count() > self.solve_count():
                current_rank += 1
        
        return current_rank, valid_members

        
    def is_discord_linked(self, connection = None, data = None) -> bool:

        """
        Returns true if the account is linked to a project euler account, 
        that is, if there is an entry in the database with the corresponding discord_id
        """
        
        dis_id = self.discord_id()
        
        if self._username is not None:
            return True
        
        if data is None:
            temp_query = f"SELECT * FROM members WHERE discord_id='{dis_id}';"
            data = pe_database.query_option(temp_query, connection)

        return len(data) >= 1 and dis_id != ""


    def is_account_in_database(self, connection = None) -> bool:

        """
        Returns whether a given member is in the database.
        """

        key_id, value_id = self.identity()
        temp_query = f"SELECT * FROM members WHERE {key_id}='{value_id}';"
        
        return len(pe_database.query_option(temp_query, connection)) >= 1
        

    def have_solves_changed(self) -> bool:
        """
        Are the solves of this member not the same on the website and in the database.
        """
        return not (self.pe_solve_count() == self.database_solve_count())
    

    def have_awards_changed(self) -> bool:
        """
        Are the awards of this member not the same on the website and in the database.
        """
        return not (self.pe_award_count() == self.database_award_count())
    

    def have_kudos_changed(self) -> bool:
        """
        Are the kudos of this member not the same on the website and in the database.
        """
        return not (self.pe_kudo_count() == self.database_kudo_count())
    

    def get_new_solves(self) -> List[int]:

        """
        Returns a list of the problems that have just been solved by a member.
        """

        if not self.have_solves_changed():
            return []
        
        project_euler_data = self.pe_solve_array()
        database_data = self.database_solve_array()
        
        max_len = len(project_euler_data)
        
        new_solves = []
        
        for i in range(max_len):
            
            if not project_euler_data[i]:
                continue
            
            if project_euler_data[i] == True and (i >= len(database_data) or database_data[i] == False):
                new_solves.append(i + 1)
            
        return new_solves
    

    def get_new_kudos(self) -> List[Tuple[int, int]]:

        """
        Returns a list of tuples. Each element has the format: (post_id, new_number_of_kudos)
        """

        if not self.have_kudos_changed():
            return []
        
        project_euler_data = self.pe_kudo_array()
        database_data = self.database_kudo_array()
        
        database_dict = {el[0]: el[1] for el in database_data}
        
        new_kudos = []
        
        for post in project_euler_data:
            
            post_id = post[0]
            post_kudos = post[1]
            
            if post_id not in database_dict.keys():
                new_kudos.append(post)
            elif post_kudos != database_dict[post_id]:
                new_kudos.append((post_id, post_kudos - database_dict[post_id]))
            
        return new_kudos
    

    def get_new_awards(self) -> Tuple[List[int], List[int], List[int]]:

        """
        Get a 3-tuple (one element for each category of awards) each element containing a list of the indexes
        of newly acquired awards.
        """

        if not self.have_awards_changed():
            return [], [], []
        
        project_euler_data = self.pe_award_array()
        database_data = self.database_award_array()
        
        first_len = len(project_euler_data[0])
        second_len = len(project_euler_data[1])
        third_len = len(project_euler_data[2])
        
        new_awards = ([], [], [])
        
        for i in range(first_len):
            if project_euler_data[0][i] == True and database_data[0][i] == False:
                new_awards[0].append(i)
            
        for i in range(second_len):
            if project_euler_data[1][i] == True and database_data[1][i] == False:
                new_awards[1].append(i)

        for i in range(third_len):
            if project_euler_data[2][i] == True and database_data[2][i] == False:
                new_awards[2].append(i)
            
        return new_awards
        

    def push_kudo_to_database(self) -> None:

        """
        Updates the kudo database according to the kudos on Project Euler's kudo page.
        """

        kudos = self.pe_kudo_array()
        
        formatted = "|".join(list(map(
            lambda el: "n".join(list(map(str, el))), kudos
        )))
    
        temp_query = f"INSERT INTO pe_posts (username, posts_number, kudos, posts_list) \
            VALUES ('{self.username()}', 0, {self.kudo_count()}, '{formatted}');"

        pe_database.query_single(temp_query)


    def push_basics_to_database(self) -> None:

        """
        Updates the database with basic information that were collected about the member.
        """

        solved = self.pe_solve_count()
        solve_list = "".join([
            "01"[boolean] for boolean in self.pe_solve_array()
        ])
        
        username = self.username()
        nickname = self.nickname()
        country = self.country()
        language = self.language()
        
        if not self.is_account_in_database():
            awards_array = self.pe_award_array()
            awards = self.pe_award_count()
            awards_list = "|".join([
                "".join(["01"[b] for b in awards_array[0]]),
                "".join(["01"[b] for b in awards_array[1]]),
                "".join(["01"[b] for b in awards_array[2]])
            ])
            
            temp_query = f"INSERT INTO members (username, nickname, country, language, solved, \
                solve_list, discord_id, awards, awards_list, private) VALUES (\
                '{username}', '{nickname}', '{country}', '{language}', \
                {solved}, '{solve_list}', '', {awards}, '{awards_list}', 0);"
                
        else:
            temp_query = f"UPDATE members SET nickname='{nickname}', \
                country='{country}', language='{language}', solved={solved},\
                solve_list='{solve_list}' WHERE username='{username}';"
                
        # print(temp_query)
        pe_database.query_single(temp_query)
        

    def push_awards_to_database(self) -> None:

        """
        Updates the database with information about the awards of the member.
        """

        username = self.username()
        
        awards_array = self.pe_award_array()
        awards = self.pe_award_count()
        awards_list = "|".join([
            "".join(["01"[b] for b in awards_array[0]]),
            "".join(["01"[b] for b in awards_array[1]]),
            "".join(["01"[b] for b in awards_array[2]])
        ])
        
        temp_query = f"UPDATE members SET awards={awards}, \
            awards_list='{awards_list}' WHERE username='{username}';"

        pe_database.query_single(temp_query)
        

    @staticmethod
    def members_friends() -> list:

        """
        Returns a list of all the members in the friend list of the bot on project euler
        """

        project_euler_data = ProjectEulerRequest("https://projecteuler.net/minimal=friends", True)
        
        usernames = list(map(
            lambda x: x.split("##")[0],
            project_euler_data.response.split("\n")
        ))
        
        result_list = []
        
        for username in usernames:
            
            if username == "":
                continue
            
            current = Member(username)
            current.update_from_friend_list(project_euler_data)
            
            result_list.append(current)
            
        return result_list
    

    @staticmethod
    def members_database() -> list:

        """
        Returns a list of all the members in the friend list of the bot in the database
        """

        database_data = pe_database.query_single("SELECT * FROM members;")

        usernames = list(map(
            lambda member: member["username"],
            database_data
        ))
        
        result_list = []
        
        for username in usernames:
            
            if username == "":
                continue
            
            current = Member(username)
            current.update_from_database(data = database_data)
            
            result_list.append(current)
            
        return result_list
    

    @staticmethod
    def members() -> list:
        
        """ 
        Returns a list of all the members that the bot has ever heard of. A list of `pe_api.Member` objects 
        """

        database_data = pe_database.query_single("SELECT * FROM members;")
        project_euler_data = ProjectEulerRequest("https://www.projecteuler.net/minimal=friends")

        database_usernames = list(map(
            lambda member: member["username"],
            database_data
        ))
        
        project_euler_usernames = list(map(
            lambda x: x.split("##")[0],
            project_euler_data.response.split("\n")
        ))
        
        result_list = []
        
        for username in project_euler_usernames:
            
            if username == "":
                continue
        
            current = Member(username)
            current.update_from_friend_list(project_euler_data)
            
            if username in database_usernames:
                current.update_from_database(data = database_data)
                
            result_list.append(current)
            
        return result_list
    

    def solved_problems(self) -> List[int]:
        """
        Returns a list like [102, 105] if the member has solved only 102 and 105
        """       
        solves = []
        for index, solved in enumerate(self.solve_array()):
            if solved:
                solves.append(index + 1)
        return solves


    def unsolved_problems(self) -> List[int]:
        """
        Returns a list like [763] if the member only has 763 left to
        """
        not_solves = []
        for index, solved in enumerate(self.solve_array()):
            if not solved:
                not_solves.append(index + 1)
        return not_solves
    

    def make_problem_unsolved(self, problem: int) -> None:

        """
        Takes a member and removes one its solves. Particularly useful for testing and debugging.
        """

        cur_solves = "".join(["01"[b] for b in self.pe_solve_array()])
        cur_solves = cur_solves[:(problem - 1)] + "0" + cur_solves[(problem - 1) + 1:]

        temp_query = f"UPDATE members SET solve_list = '{cur_solves}', solved = {self.solve_count() - 1} \
            WHERE username = '{self.username()}';"

        pe_database.query_single(temp_query)
        


def update_process() -> Optional[List[Dict[str, Any]]]:
    
    members = Member.members()
    skipped_member_count = 0
    
    new_changes = []
    
    member: Member
    for member in members:
        
        if member.have_solves_changed():
            
            new_solves = member.get_new_solves()
            console.log(f"New solve(s) for {member.username()}: {new_solves}")
            member.push_basics_to_database()

            new_awards = None
            if member.have_awards_changed():
                new_awards = member.get_new_awards()
                console.log(f"New award(s) for {member.username()}: {new_awards}")
                member.push_awards_to_database()
            
            new_changes.append({"member": member, "solves": new_solves, "awards": new_awards})
            
        else:
            skipped_member_count += 1
            
    console.log(f"Skipped {skipped_member_count} members")
    return new_changes



def push_solve_to_database(member: Member, solve: PE_Problem):

    pb_def = problem_def(solve.problem_id)
    position = pb_def[3]

    temp_query = "INSERT INTO solves (member, problem, solve_date, position) VALUES ('{0}', {1}, datetime('now'), {2})"
    temp_query = temp_query.format(member.username(), solve.problem_id, position)
    pe_database.query_single(temp_query)






# Return array of the form ['n', 'Problem title', Unix Timestamp of publish, 'nb of solves', '0']
# Careful as all values in the array are string, not ints
def problem_def(n):
    data = ProjectEulerRequest(BASE_URL.format("problems")).response
    lines = data.split("\n")
    pb = lines[n].replace("\r", "")
    specs = pb.split("##")
    return specs


# Return array of the form [problem_1, problem_2, ...., problem_last]
# With each problem being of the kind ['n', 'Problem title', Unix Timestamp of publish, 'nb of solves', '0']
# Careful as all values in the array are string, not ints
def problems_list():
    data = ProjectEulerRequest(BASE_URL.format("problems")).response.split("\n")
    data = list(map(lambda element: element.replace("\r", "").split("##"), data))
    return data


# Return last problem available, including the ones in the recent tab
def last_problem():
    data = ProjectEulerRequest(BASE_URL.format("problems")).response
    return len(data.split("\n")) - 2


def last_problem_database():
    data = pe_database.query_single("SELECT MAX(len) AS most_solve FROM (SELECT LENGTH(solve_list) AS len FROM members) AS T;")
    return data[0]["most_solve"]



# Returns False if discord_id is not in the database, else returns the project euler username
def project_euler_username(discord_id, connection=None) -> str:

    temp_query = f"SELECT * FROM members WHERE discord_id='{discord_id}';"
    data = pe_database.query_option(temp_query, connection=connection)

    if len(data) < 1:
        return ""

    return data[0]["username"]


# returns a list of the form [profile1, profile2, profile3, ...]
# with profile1 of the form [username, nickname, country, language, solved, level, list of solve]
# and list of solve being of the form 1111100010000111 and so on
# Note that all values are strings
def get_all_profiles_on_project_euler():

    url = BASE_URL.format("friends")
    data = ProjectEulerRequest(url).response
    if data is None:
        pass

    members = list(map(lambda x: x.split("##"), data.split("\n")))
    return members[:-1]


# returns a list of the form [username1, username2, username3, ...]
def get_all_usernames_on_project_euler():

    profiles = get_all_profiles_on_project_euler()
    return list(map(lambda x: x[0], profiles))


# Essentially does the same thing as get_all_members_who_solved, but returns the entire profiles
# Returns a list with format [[username1: str, discord_id1: str], [username2: str, discord_id2: str], ....]
def get_all_discord_profiles_who_solved(problem: int):

    solvers = []

    profiles = get_all_profiles_in_database()

    for k in profiles.keys():
        profile = profiles[k]
        
        if len(profile["solve_list"]) >= problem and profile["solve_list"][problem - 1] == "1" and profile["discord_id"] != "":
            solvers.append([profile["username"], profile["discord_id"]])

    return solvers


# return a binary string like "111110001100..." with every 1 marking a solve
# use a project euler request, not a request to the database (should not change anything)
def problems_of_member(username):

    url = BASE_URL.format("friends")
    data = ProjectEulerRequest(url).response
    if data is None:
        pass

    members = list(map(lambda x: x.split("##"), data.split("\n")))

    usernames = list(map(lambda x: x[0], members))
    if username not in usernames:
        return None

    member_solves = members[usernames.index(username)][6]

    return member_solves


# returns a list of all the profiles in the database 
def get_all_profiles_in_database():
    return dbqueries.single_req("SELECT * FROM members;")


# return a list of all the names of the awards
def get_awards_specs():
    url = NOT_MINIMAL_BASE_URL.format("progress;show=awards")
    data = ProjectEulerRequest(url).response
    soup = BeautifulSoup(data, 'html.parser')

    awards_container = soup.find(id="awards_section").find_all("div", recursive=False)

    div1 = awards_container[0]
    div2 = awards_container[1]
    div3 = awards_container[2]

    # problem_awards = div1.find_all(class_="award_box")
    # solves_problem = [1 if len(problem.find_all(class_="smaller green strong")) == 1 else 0 for problem in problem_awards]

    # problem_publication = div2.find_all(class_="award_box")
    # solves_publication = [1 if len(problem.find_all(class_="smaller green strong")) == 1 else 0 for problem in problem_publication]
    
    # forum_awards = div3.find_all(class_="award_box")
    # solves_forum = [1 if len(problem.find_all(class_="smaller green strong")) == 1 else 0 for problem in forum_awards]

    all_awards = []

    problem_awards = div1.find_all(class_="tooltip inner_box")
    all_awards.append([problem.find_all(class_="strong")[0].text for problem in problem_awards])

    problem_publication = div2.find_all(class_="award_box")
    all_awards.append([problem.find_all(class_="strong")[0].text for problem in problem_publication])

    forum_awards = div3.find_all(class_="award_box")
    all_awards.append([problem.find_all(class_="strong")[0].text for problem in forum_awards])

    # d_problems = soup.find(id="forum_based_awards_section").find_all(class_="tooltip inner_box")
    
    # all_awards.append([problem.find_all(class_="strong")[0].text for problem in d_problems])

    return all_awards


# Get the solves of the last few days in the database
def get_solves_in_database():

    # connection = dbqueries.open_con()
    connection = pe_database.open_connection()

    temp_query = "SELECT * FROM solves;"
    # if days_count == 0:
    #     temp_query = "SELECT * FROM solves"
    # else:
    #     temp_query = "SELECT * FROM solves WHERE DATE(solve_date) BETWEEN DATE(CURRENT_DATE() - INTERVAL {0} DAY) AND DATE(CURRENT_DATE());"
    #     temp_query = temp_query.format(days_count)
    
    data = pe_database.query(temp_query, connection)
    # data = dbqueries.query(temp_query, connection)
    pe_database.close_connection(connection)
    # dbqueries.close_con(connection)

    return data


# Get the global solves in the database
def get_global_solves_in_database():

    connection = pe_database.open_connection()

    temp_query = "SELECT id, solves, date_stat FROM global_stats"

    data = pe_database.query(temp_query, connection)
    pe_database.close_connection(connection)

    return data 


# Get the current global stats on the website
def get_global_stats():

    # Basic script to get the html code on a page
    problem_url = NOT_MINIMAL_BASE_URL.format("problem_analysis")
    problem_data = ProjectEulerRequest(problem_url).response
    problem_soup = BeautifulSoup(problem_data, 'html.parser')

    # This tag represents the column we wants
    problems = problem_soup.find_all(class_="equal_column")
    problems = list(map(lambda x: x.text, problems)) # Get the text of elements, no html tags
    problems = list(filter(lambda x: x != "Solved Exactly", problems)) # Remove colum names

    # Problem count
    problem_count = sum([(i + 1) * int(problems[i]) for i in range(len(problems))])
    
    # Again, basic requests to get html code
    level_url = NOT_MINIMAL_BASE_URL.format("levels")
    level_data = ProjectEulerRequest(level_url).response
    level_soup = BeautifulSoup(level_data, 'html.parser')

    # Format all this data
    levels = level_soup.find_all(class_="small_notice")
    levels = list(map(lambda x: x.text.split()[0], levels)) # format <div>4054 members</div>
    
    # Get levels count
    level_count = sum([(i + 1) * int(levels[i]) for i in range(len(levels))])    

    # Basic script to get the awards stats
    award_url = NOT_MINIMAL_BASE_URL.format("awards")
    award_data = ProjectEulerRequest(award_url).response
    award_soup = BeautifulSoup(award_data, 'html.parser')

    # Formatting the data
    awards = award_soup.find_all(class_="small_notice")
    awards = list(map(lambda x: x.text.split()[0], awards))
    
    # Award count
    award_count = sum(list(map(int, awards)))

    return [problem_count, level_count, award_count]


# Update the database with global statistics
def update_global_stats():

    # Open connection to the database
    # connection = dbqueries.open_con()
    connection = pe_database.open_connection()

    # The query to retrieve saved statistics
    temp_query = "SELECT * FROM global_constants;"
    # previous_data = dbqueries.query(temp_query, connection)
    previous_data = pe_database.query(temp_query, connection=connection)

    # Ensure the retrieve was successful
    if len(previous_data) == 1:
        previous_data = previous_data[0]
    else:
        pe_database.close_connection(connection)
        # dbqueries.close_con(connection)
        return False

    # Assert the current day has not already been retrieved
    current_day = datetime.datetime.now(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")
    last_date = datetime.datetime.strptime(previous_data["saved_date"], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")

    if current_day == last_date:
        return False

    # Get today's statistics
    problem_count, level_count, award_count = get_global_stats()

    # Compute the difference for each stat
    problem_diff = problem_count - previous_data["solves_count"]
    level_diff = level_count - previous_data["levels_count"]
    award_diff = award_count - previous_data["awards_count"]

    # If the cache is still the same, no need to update right now
    if problem_diff == 0 and level_diff == 0 and award_diff == 0:
        return False

    # And bring it back in the database
    temp_query = "INSERT INTO global_stats (solves, levels, awards, date_stat) VALUES ({0}, {1}, {2}, datetime('now'));"
    temp_query = temp_query.format(problem_diff, level_diff, award_diff)
    pe_database.query(temp_query, connection)
    # dbqueries.query(temp_query, connection)

    # Update the last data
    temp_query = "UPDATE global_constants SET solves_count = {0}, levels_count = {1}, awards_count = {2}, saved_date = datetime('now');"
    temp_query = temp_query.format(problem_count, level_count, award_count)
    pe_database.query(temp_query, connection)
    # dbqueries.query(temp_query, connection)


    # Alert my phone that everything has went as planned
    phone_api.bot_success("Added stats for day " + current_day)
    pe_database.close_connection(connection)

    return True # Everything went fine


def get_fastest_solvers(problem: int):

    page_url = NOT_MINIMAL_BASE_URL.format(f"fastest={problem}")
    solvers_data = ProjectEulerRequest(page_url).response
    solvers_soup = BeautifulSoup(solvers_data, 'html.parser')

    if "No data available" in solvers_soup.text:
        return {}
    
    rows = solvers_soup.find_all(class_="grid")[0].find_all("tr")
    number_of_solvers = len(rows) - 1

    data = {}

    for rank, element in enumerate(rows, start = 0): # starts at 0 because we want to exclude row "0" being the "user, country, language, time"
        
        lines = element.find_all("td")

        if len(lines) != 5:
            continue

        """
        lines[0] = rank
        lines[1] = username
        lines[2] = country
        lines[3] = language
        lines[4] = time
        """

        username = lines[1].text

        try_nickname = lines[1].find_all("span")
        if len(try_nickname) != 0:
            username = lines[1].find("span").get("title")

        solve_time_string = lines[4].text

        correspondances = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
            "week": 604800,
            "year": 31536000
        }

        solve_time = 0
        for k in correspondances.keys():
            for part_str in solve_time_string.split(", "):
                
                if k in part_str:
                    solve_time += correspondances[k] * int(part_str.split()[0])

        data[str(rank)] = {"username": username, "solve_time": solve_time}

    return data


def update_fastest_solves(starting_problem: int = 277):

    last_pb = last_problem()

    data_filename = "saved_data/fastest_solves.json"

    with open(data_filename, "r") as f:
        whole_data = json.load(f)

    console.log("Refreshing data for solvers.")

    wait_time = 1

    for problem in range(starting_problem, last_pb + 1):
        
        data = get_fastest_solvers(problem)
        whole_data[problem] = data
        
        console.log(problem)
        time.sleep(wait_time)

    with open(data_filename, "w") as f:
        json.dump(whole_data, f, indent=4)




if __name__ == "__main__":

    m = Member(_username = "Teyzer18")
    print(m.has_solved(906))

    print(last_problem_database())

    # minimals = ""

    # l = 903

    # for i in range(1, l + 1):
    #     txt = ProjectEulerRequest(BASE_URL.format(str(i))).response
    #     minimals += f"Problem #{i}" + txt + "\n\n"
    #     console.log(i)

    # with open("saved_data/minimals.txt", "w") as f:
    #     f.write(minimals)
    
    
