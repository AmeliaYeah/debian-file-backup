import colorama, time, sys, os
registry = "/etc/debian-disk-backup.reg"
backup_true_directory_var = "BACKUP_TRUE_PWD"
backup_loc_name = "/usr/share/debian-files-backup"
required_packages = ["vim", "zip", "rsync"]

def pretty_print(msg, type=None):
    msg_icon = colorama.Fore.GREEN+"+"
    if type == "err":
        msg_icon = colorama.Fore.RED+"-"
    elif type == "warn":
        msg_icon = colorama.Fore.YELLOW+"!"
    elif type == "fatal":
        msg_icon = colorama.Fore.RED+colorama.Style.BRIGHT+"!!!"
        msg = colorama.Fore.RED + msg

    print(f"{colorama.Fore.WHITE+colorama.Style.BRIGHT}[{msg_icon+colorama.Fore.WHITE}] {msg+colorama.Style.RESET_ALL}")
    if type == "fatal":
        print(colorama.Fore.RED+colorama.Style.BRIGHT+"Fatal error; aborting..."+colorama.Style.RESET_ALL)
        exit()


def animate_print(msg, time_sleep):
    waiting_for_color_code = False
    for char_index in range(len(msg)+1):
        start = "\r"+colorama.Fore.WHITE+colorama.Style.BRIGHT
        try:
            print(start+msg[:char_index], end="")
            sys.stdout.flush() #so it actually prints char-by-char

            #only sleep when we're printing an ascii char
            #(to avoid the printing getting slower due to the color code being printed our char-by-char aswell)
            if not waiting_for_color_code:
                time.sleep(time_sleep)
            elif msg[char_index] == "m": #this means the char code is done
                waiting_for_color_code = False

            if char_index < len(msg)-1 and msg[char_index].encode("ascii") == b"\x1b" and msg[char_index+1] == "[": #its a char code bois
                waiting_for_color_code = True
        except KeyboardInterrupt:
            print(start+msg, end="")
            break

    print(colorama.Style.RESET_ALL)


def is_confirmed(prompt, default_is_y=True):
    if default_is_y:
        choose_prompt = colorama.Fore.RED+colorama.Style.BRIGHT+"Y"+colorama.Style.RESET_ALL+colorama.Fore.WHITE+", n"
    else:
        choose_prompt = "y, "+colorama.Fore.RED+colorama.Style.BRIGHT+"N"+colorama.Style.RESET_ALL+colorama.Fore.WHITE

    try:
        response = input(colorama.Style.BRIGHT+colorama.Fore.WHITE+prompt+" "+colorama.Style.NORMAL+"["+choose_prompt+"]: "+colorama.Style.RESET_ALL).strip().lower()
    except KeyboardInterrupt:
        response = ""
        print("\n")

    if response == "":
        return default_is_y
    elif response == "n" or response == "y":
        return response == "y"
    else:
        pretty_print(f"Unknown input: {colorama.Fore.CYAN+response+colorama.Style.RESET_ALL}", "warn")
        return is_confirmed(prompt, default_is_y)

def system(cmd):
    res = os.system(cmd)
    if res != 0:
        raise Exception(f"Failed execution of command '{cmd}'; Error code {res}")


def parse_shorthand_directory(dir):
    #notice how we don't use os.getcwd(), but rather the "true directory" var specified previously?
    current_dir_raw = os.environ[backup_true_directory_var]
    current_dir = current_dir_raw if not current_dir_raw.endswith("/") else current_dir_raw[:-1] #remove trailing slash

    #NOTE: important that "../" checks go before "./" checks, since...yeah.
    dir = dir.replace("../", "/".join(current_dir.split("/")[:-1])+"/") #for the previous-directory shorthand
    dir = dir.replace("./", current_dir+"/") #for the current-directory shorthand
    dir = dir.replace("~/", os.environ["HOME"]+"/") #just guess

    if not dir.startswith("/"): #they're likely using a file in the CWD
        dir = f"{current_dir}/{dir}"

    return dir


valid_locations_delim = ">>SPLIT<<"
base_registered = [
    registry+valid_locations_delim+"file",
    "/etc/apt/sources.list"+valid_locations_delim+"file",
    backup_loc_name+valid_locations_delim+"directory"
]
def get_valid_locations(locations, is_dir):
    if locations == None:
        return []

    valid = []
    loc_type = "directory" if is_dir else "file"
    for location_raw in locations:
        location = parse_shorthand_directory(location_raw)

        location_err_prefix = colorama.Fore.CYAN+location+colorama.Fore.WHITE
        check = os.path.isdir(location) if is_dir else os.path.isfile(location)
        if not check:
            pretty_print(f"{location_err_prefix} is not a valid {loc_type}", "err")
            continue

        generated = location+valid_locations_delim+loc_type
        if generated in base_registered:
            pretty_print(f"The modification of {location_err_prefix} is off limits.", "err")
            continue

        valid.append(generated)

    return valid


def setup():
    if os.path.isdir(backup_loc_name):
        return

    pretty_print("The backup script looks like it hasn't been properly set up yet.", "err")
    if not is_confirmed("Set it up now?"):
        return


    pretty_print("Making the registry file..")
    system(f"touch {registry}")
    system(f"chmod 600 '{registry}'") #only root can read/write from the file


    pretty_print("Performing a sanity check for all the required debian packages...")
    for required in required_packages:
        pretty_print(f"Checking package {colorama.Fore.BLUE}{required}{colorama.Fore.WHITE}...")
        try:
            system(f"dpkg -s {required} 2>/dev/null >/dev/null")
        except:
            pretty_print("Package: "+colorama.Fore.YELLOW+required+colorama.Fore.RED+" does not exist!", "warn")
            system(f"apt install -y {required}")



    pretty_print(f"Creating directory {colorama.Fore.CYAN+backup_loc_name+colorama.Fore.RESET}...")
    system(f"cp -r . {backup_loc_name}")
    system(f"chmod -R 711 {backup_loc_name}") #711 translates to rwx--x--x


    backup_file_name = "/usr/bin/backup"
    if os.path.isfile(backup_file_name):
        if not is_confirmed(f"The file {colorama.Fore.CYAN+backup_file_name+colorama.Fore.RESET} already exists. Would you like to overwrite it?", False):
            backup_file_name = "/usr/bin/" + input("Please enter a new name for the file: /usr/bin/").strip()

    pretty_print(f"Creating file {colorama.Fore.CYAN+backup_file_name+colorama.Fore.RESET}..")
    with open(backup_file_name, "w") as f:
        f.write(f"export {backup_true_directory_var}=\"${{PWD}}\" && cd {backup_loc_name} && sudo -E ./backup.py \"$@\" && cd ${{{backup_true_directory_var}}}")
        system(f"chmod 711 '{backup_file_name}'")
        
    system(f"{backup_file_name} -f {backup_file_name}") #so the backup file stays preserved
    pretty_print("Setup has successfully completed :)")
    pretty_print(f"You can feel free to {colorama.Fore.BLUE}rm -rf{colorama.Fore.WHITE} the directory {colorama.Fore.CYAN}{os.getcwd()}{colorama.Fore.WHITE} now! Just run the command 'backup' in your terminal :)")
    exit()
