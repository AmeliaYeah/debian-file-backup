#!/usr/bin/python3

# good on you for reading the source code ;)
# keep it up, it's good practice.

import os
try:
    import subprocess, tempfile, sys
    from argparse import ArgumentParser
    from backup_lib import *
    from colorama import Fore, Style
except:
    print("Uh oh! Looks like you're missing a dependancy. Let me fix that for you...")
    if os.system("pip3 install -r pip_requirements.txt") != 0:
        print("DOUBLE UH OH! It appears something went wrong with execution. You're on your own for this one.")
        exit()
    else:
        print("Done!! Will restart now :)")
        os.system(f"./backup.py {' '.join(sys.argv)}") #restart the program
        exit()


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
restore_script_buffer = ""
def compile():
    global restore_script_buffer
    if args.compile == None:
        return


    directory_raw = get_valid_locations([args.compile], True)
    if directory_raw == []:
        return

    directory = directory_raw[0].split(valid_locations_delim)[0]
    def format_install_section(command, to_install):
        global restore_script_buffer
        seperator = "\n"+command+" "

        restore_script_buffer += f"echo 'Running: {Fore.YELLOW+Style.BRIGHT}{command}{Style.RESET_ALL}'\nsleep 1"
        install_chunks = []
        maximum_chunk_length = 60 #amount of packages to install per 'install' line

        current_chunk = []
        register_chunk = lambda: install_chunks.append(" ".join(current_chunk))
        for package in to_install:
            if len(current_chunk) > maximum_chunk_length:
                register_chunk()
                current_chunk = []
            else:
                current_chunk.append(package)

        if len(current_chunk) > 0:
            register_chunk() #just to register the last one if it wasn't able to get registered by the for loop

        restore_script_buffer += seperator+seperator.join(install_chunks)+"\n"




    animate_print("BACKUP PROCESS INITIATING...", 0.05)
    animate_print("=============================", 0.05)
    print("")
    pretty_print(f"Mount point: {Fore.GREEN}{directory}")

    if args.dry_run:
        pretty_print(f"{Fore.YELLOW}RUNNING IN DRY-RUN MODE")

    animate_print("=============================", 0.05)
    print("")





    ##############################################################
    ##               Start backing up the files                 ##
    ##############################################################

    pretty_print("Copying all the registered files/directories into the backup...")
    print("")

    if not args.dry_run:
        rsync_files_name = "rsync_files.txt"
        with open(registry, "r") as f:
            files_raw = [line.strip() for line in f.readlines()]+base_registered
            with open(rsync_files_name, "a") as files:
                for file in files_raw:
                    file_data = file.split(valid_locations_delim)
                    file_name = file_data[0]
                    file_type = file_data[1]

                    if file_type == "directory":
                        for root, dirs, files_walked in os.walk(file_name):
                            for file in files_walked:
                                files.write(f"{root}/{file}\n") #god rsync why couldn't you just be a normal person
                    elif file_type == "file":
                        while file_name.endswith("/"):
                            file_name = file_name[:-1]
                        files.write(file_name+"\n")
                    else:
                        print(f"Unknown file type {Fore.RED}{file_type}{Fore.WHITE} for file: {Fore.CYAN}{file_name}{Fore.WHITE}. Skipping...")
                        continue

        system(f"rsync --files-from={rsync_files_name} -a -H -A -X / '{directory}/files-backup'")
        system(f"bash -c \"cd {directory} && zip -r -9 ./back.zip ./files-backup 2>/dev/null >/dev/null\"") #zip -r is a pain in the a** for absolute paths so here fine have it your way dude
        system(f"rm -rf '{directory+'/files-backup'}'")
        system(f"rm '{rsync_files_name}'")

    
    restore_script_buffer += f"""#!/bin/bash
    #check if user is root
    if [ "$EUID" -ne 0 ]
        then echo '{Fore.RED}Please run as root{Style.RESET_ALL}'
        exit
    fi

    #restore their files (and ensure the dependancies are installed)
    apt update
    apt install -y {' '.join(required_packages)}
    unzip back.zip
    rsync -avhu --progress ./files-backup /

    #clean up
    rm back.zip
    rm -rf ./files-backup
    apt update


    #check for internet connection
    ifconfig
    read -p 'Press enter when you have ensured that this device is connected to the internet.' dummy_var
    clear

    #setup my backup script
    git clone https://github.com/AmeliaYeah/debian-file-backup
    cd debian-file-backup
    chmod +x ./backup.py
    pip3 install -r pip_requirements.txt
    sudo ./backup.py

    #clean up the backup script repo
    cd ..
    rm -rf debian-file-backup


    #handle restoring all the packages that were installed in the old system
    """.replace("    ","") #look man idk why the tabs are included ugh




    ##############################################################
    ##               Start backing up the repos                 ##
    ##############################################################

    pretty_print("Beginning backup of APT local repository....")
    if not args.dry_run:
        not_found = []
        to_install = []

        apt_out = subprocess.check_output(["apt", "list", "--installed"], stderr=subprocess.DEVNULL)
        apt_list = apt_out.decode("ascii").split("\n")
        for package_index in range(len(apt_list)):
            print(f"\r{Fore.WHITE}Verified {package_index+1}/{len(apt_list)} packages{Style.RESET_ALL}", end="")
            package_data = apt_list[package_index].strip().split("/")
            
            package = package_data[0]
            if package == "Listing..." or package == "":
                continue

            if package_data[1].endswith("[installed,local]"): #check if the package was NOT installed from the repositories
                not_found.append(package)
            else:
                to_install.append(package)

        print("\n")
        format_install_section("apt install -y", to_install)
        if len(not_found) > 0:
            restore_script_buffer += f"\necho 'The following packages were determined to not be in the local repository list: {Fore.GREEN+Style.BRIGHT}{', '.join(not_found)}{Style.RESET_ALL}. Maybe you got them externally?'\nread -p 'Press enter to continue: ' dummy_var\n"
    else:
        restore_script_buffer += "\napt install -y [all installed packages]"




    pretty_print("Beginning backup of local PIP repository....")
    if not args.dry_run:
        pip_packages = subprocess.check_output(["pip", "freeze"], stderr=subprocess.DEVNULL).decode("ascii").split("\n")[:-1] #we skip the last element since it's just whitespace.
        format_install_section("pip install",[package.strip() for package in pip_packages])
    else:
        restore_script_buffer += "\npip install [all pip packages]"






    ##############################################################
    ##                      All done!                           ##
    ##############################################################
    
    print("\n")
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
