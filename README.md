# debian-file-backup

This was just a simple python script I developed for personal use out of spite for a lack of programs that handle full-system backups.

It's essentially just a glorified, user-friendly terminal interface where a central "registry" of files and directories are stored into a ZIP file, which then (with the help of the generated restore.sh script) will automatically be unzipped and placed back into your file system.

It also handles automatically backing up your entire apt and pip repositories (I could add more repos obviously but these are the two I use mainly), so that when you use your new machine you don't have to deal with the headache of installing old packages you probably forgot about.

All-in-all: It's pretty straightforward, but you might be able to make good use of it ;)

*Note:* This **ONLY** works with debian. Though, it's possible to make it work with other Linux distributions provided you fix the dependancy on apt. It was designed for systems using the linux kernel however, so Mac and Windows users; you're out of luck here.

**IMPORTANT:** Make sure that, upon doing `zip -v | head -n 2`, it says you are using _Info-Zip_. Otherwise, file permissions being preserved might not be guaranteed.
