#!/usr/bin/python3
import os, subprocess, tempfile
from argparse import ArgumentParser
from backup_lib import *
from colorama import Fore, Style


#handle arguments
footer = f"{Fore.RED+Style.BRIGHT}NOTE: {Style.RESET_ALL+Fore.WHITE}This was only intended for Debian-based systems. It may still work on other Linux distributions (provided you take care of the portions of the script which use APT), but just keep this in mind.{Style.RESET_ALL}"
parser = ArgumentParser(prog="debian-system-backup", description="Automatically creates backups", epilog=footer)

parser.add_argument("--dry-run", action="store_true", help="Don't actually do anything; only print what would've happened.")
parser.add_argument("--compile", help="Compile everything into the specified directory.")

backup_items = parser.add_argument_group("backups", description="Commands that back up specific items")
backup_items.add_argument("--directory", "-d", nargs="+", help="Registers/deregisters a directory that will be synced with rsync upon compilation")
backup_items.add_argument("--file", "-f", nargs="+", help="Registers/deregisters a file that will be added to the compiled backup")
backup_items.add_argument("--list", "-l", action="store_true", help="Lists all the files/directories marked to be backed up.")

try:
    args = parser.parse_args()
except Exception as e:
    pretty_print(e, "fatal")



#run checks before executing further
def do_checks():
    if os.geteuid() != 0:
        pretty_print("You must be root to do this.", "fatal")
    if "SUDO_USER" not in os.environ.keys():
        pretty_print("Due to the programming of this application, it is required that in order to run it as root you use 'sudo' specifically. Please try this again.", "fatal")
    if __name__ != "__main__":
        pretty_print("This script cannot be imported. It can only be executed.", "fatal")

    #run the setup if required
    try:
        setup()
    except Exception as e:
        pretty_print(f"Error occured during setup: {e}", "fatal")

do_checks()



#list the contents of the registry and exit if asked to
if args.list:
    list_tmp = tempfile.mkstemp()[1]
    system(f"chmod 744 '{list_tmp}'") #rwxr--r--
    with open(registry, "r") as f:
        with open(list_tmp, "w") as tmp:
            tmp.write("\n".join([line.strip().split(valid_locations_delim)[0] for line in f.readlines()]))

    system(f"sudo -u {os.environ['SUDO_USER']} vim {list_tmp}")
    os.remove(list_tmp)
    exit()



#handle registration of the directories and files
def handle_files_and_directories():
    locations = get_valid_locations(args.file, False)+get_valid_locations(args.directory, True)
    if locations == []:
        return
    with open(registry, "r") as handle:
        buffer = [line.strip() for line in handle.readlines()]

    for location in locations:
        location_split = location.split(valid_locations_delim)
        file_name = Style.BRIGHT+Fore.CYAN+location_split[0]
        file_type = location_split[1]
        if location not in buffer:
            pretty_print(f"Wrote {file_type} {file_name}")
            buffer.append(location)
        else:
            pretty_print(f"Removed {file_type} {file_name}")
            buffer.remove(location)

    if not args.dry_run:
        with open(registry, "w") as write_handle:
            write_handle.write("\n".join(buffer))
    else:
        pretty_print("This was a dry-run; no changes were made.")
        

handle_files_and_directories()





#handle compiling the backups
def compile():
    if args.compile == None:
        return


    directory_raw = get_valid_locations([args.compile], True)
    if directory_raw == []:
        return

    directory = directory_raw[0].split(valid_locations_delim)[0]+"/os_backup"
    restore_script_buffer = "#!/bin/bash\n"



    animate_print("BACKUP PROCESS INITIATING...", 0.05)
    animate_print("=============================", 0.05)
    print("")
    pretty_print(f"Mount point: {Fore.GREEN}{directory}")

    if args.dry_run:
        pretty_print(f"{Fore.YELLOW}RUNNING IN DRY-RUN MODE")

    animate_print("=============================", 0.05)
    print("")


    pretty_print("Beginning backup of APT local repository....")
    restore_script_buffer += "apt install "
    if not args.dry_run:
        not_found = []

        apt_out = subprocess.check_output(["apt", "list", "--installed"], stderr=subprocess.DEVNULL)
        apt_list = apt_out.decode("ascii").split("\n")
        for package_index in range(len(apt_list)):
            print(f"\r{Fore.WHITE}Verified {package_index+1}/{len(apt_list)} packages{Style.RESET_ALL}", end="")
            package_data = apt_list[package_index].strip().split("/")
            
            package = package_data[0]
            if package == "Listing..." or package == "":
                continue

            if "[installed,local]" in package_data[1]: #check if the package was NOT installed from the repositories
                not_found.append(package)
            else:
                restore_script_buffer += package+" "

        print("\n")
        if len(not_found) > 0:
            restore_script_buffer += f"\necho 'The following packages were determined to not be in the local repository list: {Fore.GREEN+Style.BRIGHT}{', '.join(not_found)}{Style.RESET_ALL}. Maybe you got them externally?'"
    else:
        restore_script_buffer += "[LIST OF ALL INSTALLED PACKAGES]"





    pretty_print("Beginning backup of local PIP repository....")
    restore_script_buffer += "\npip install "
    if not args.dry_run:
        pip_packages = subprocess.check_output(["pip", "freeze"], stderr=subprocess.DEVNULL).decode("ascii").split("\n")
        restore_script_buffer += " ".join([package.strip() for package in pip_packages])
    else:
        restore_script_buffer += "[LIST OF ALL PIP PACKAGES]"




    backup_msg = "Copying all the registered files/directories into the backup..." #for the line seperators it needs it's own variable
    pretty_print(backup_msg)
    animate_print("="*len(backup_msg), 0.001)
    print("")
    with open(registry, "r") as f:
        files = [line.strip() for line in f.readlines()]+base_registered
    for file_raw in files:
        file_raw = file_raw.split(valid_locations_delim)
        file = file_raw[0]
        file_type = file_raw[1]

        if file_type not in ["directory", "file"]:
            pretty_print(f"Invalid file type {Fore.GREEN}{file_type}{Fore.WHITE} for file {Fore.CYAN}{file}{Fore.WHITE}", "err")
            continue

        parent_dir = directory+"/files-backup/"+"/".join(file.split("/")[:-1])
        if not args.dry_run:
            os.system(f"mkdir -p '{parent_dir}' 2>/dev/null >/dev/null") #we don't use os.mkdir() since the "-p" argument can't be specified that way
            copy_arg = "-i" if file_type == "file" else "-ri"
            system(f"cp {copy_arg} '{file}' '{parent_dir}'")


        pretty_print(f"Successfully backed up {file_type} {Fore.CYAN}{file}{Fore.WHITE} to {Fore.YELLOW}{parent_dir}{Fore.WHITE}")

    system(f"zip -r -9 '{directory}/back.zip' '{directory}/files-backup' 2>/dev/null >/dev/null")
    system(f"rm -rf '{directory+'/files-backup'}'")

    
    #final finishing touches to the script
    restore_script_buffer += """
    unzip back.zip
    rsync -avhu --progress ./files-backup /

    rm back.zip
    rm -rf ./files-backup
    """.replace("    ","") #look man idk why the tabs are included ugh

    
    print(Fore.WHITE+Style.BRIGHT+("="*len(backup_msg)+Style.RESET_ALL), end="\n\n")
    if args.dry_run and is_confirmed("Would you like to see the restore.sh script that was generated? (Since this was run in dry-run mode)"):
        script_tmp = tempfile.mkstemp()[1]
        with open(script_tmp, "w") as f:
            f.write(restore_script_buffer)
        system(f"chmod 744 '{script_tmp}'") #rwxr--r--

        system(f"sudo -u {os.environ['SUDO_USER']} vim {script_tmp}")
        os.remove(script_tmp)
    elif not args.dry_run:
        restore_script_location = directory+"/restore.sh"
        with open(restore_script_location, "w") as f:
            f.write(restore_script_buffer)
        system(f"chmod 755 '{restore_script_location}'") #rwxr-xr-x



try:
    compile()
except Exception as e:
    pretty_print(f"Error occured during compilation: {e}", "err")
pretty_print("All done! :)")
