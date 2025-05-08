import json
from get_homes_info import get_homes_info
from load_to_db import load_to_db


def main():
    # searching a particular zip code and for no pool
    url = "https://www.redfin.com/zipcode/85297/filter/pool-type=no-private"
    homes = get_homes_info(url)   # gets all homes info as a big json file

    with open("dumps/homes.json", "w") as f:
        json.dump(homes, f, indent=4)  # `indent=4` makes it pretty-printed
    # with open("dumps/homes.json", "r") as original_json:
    #     homes = json.load(original_json)
    # load_to_db(homes)


if __name__ == "__main__":
    main()
