Overseer isn't just a tool for building and exploring models. It is also a framework for developing fully features standalone applications meant to act as communication tools. Through the use of tooltips in particular and experimentation, users can learn as they play.  

Because of this, I took very seriously the need to supply the tools needed for making special restricted versions of Overseer, which I'll call **feature model releases**. The differences between a feature model release and the standard **studio edition** of Overseer is as follows:
1. Feature model releases are self contained with its own Python environment. This makes them bigger, but makes them more like Apps in that nothing more is required of the software but itself - the user does not need to have Python installed in order to open and play with a feature model release. 
2. Feature model releases 'focus inward', and do not create any files or folder on the user's computer besides the ones it comes with. 
3. The logs panel is disabled for feature model releases. 

These are currently the only *necessary* differences of feature model releases and the normal studio version of Overseer. In short, these are versions of Overseer meant to be used by folks with no assumed level of technical expertise, and who do not have any interest in using Overseer to build their own models, nor even knowledge that the software can be used that way at all. The only assumption about the user of a feature model release of Overseer is that they are a curious audience with whom you want to communicate your model. 

The rest of this section will walk you through the process of creating your own release builds. However, before proceeding, you need to be aware of a few limitations:
1. If you want to create a release build for Windows, you **must** do so **from a Windows machine**. Likewise, release builds intended for Mac OS **must be created from a Mac OS** machine. In the case of Mac OS, it should not matter whether your chip architecture if x86-64 or Arm.
2. In the case of Mac OS, your program will almost certainly be blocked initially from running on the user's computer, and they will be forced to go into their security settings and then confirm that they want to run the program anyway. There are some free ways to mitigate the inconvenience this produces for your users, but the only way to truly circumvent it is to pay Apple $100 a year in order to be a certified developer, and notarize your build after creating it with your credentials. 
# Creating Release Builds

## Preparing Your Environment
For this job, it will be best if you are running Overseer 'directly from source'. This means that you should clone the repo, create a virtual environment, and then pip install Overseer *in editor mode*! I.e. something along the lines of the following commands:

```sh
git clone https://github.com/alexbcreiner0/Overseer
cd Overseer
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

Installing Overseer with the `-e` flag is absolutely essential, because you are going to be modifying the package files a bit as you do this. If you only pip install normally, a copy of Overseer's source files will be created inside of the virtual environment, and the changes you make will be ignored. 

Additionally, make sure that you have pyinstaller installed:
```sh
pip install pyinstaller
```
## Preparing Your Build Files
The pipelines for creating feature model releases for Windows and Mac OS can be found in the release folder. However, before we look there, we should talk about how to get your files ready for doing that build. 

Normally, when Overseer is loaded for the first time, some checks are performed to make sure that the necessary files and folders are present on the user's computer. In particuler:
- If Overseer doesn't find a `config.yml` file where it thinks it should, it will create one. 
- If, based on that `config.yml` file, it doesn't find a user data folder where it thinks it should, it creates one.  

The `config.yml` file which Overseer creates is a copy of the file `config.example.yml`, found inside of the `src/overseer/defaults` directory of this repo. Similarly, the starting models which Overseer creates inside of a new user's data folder are found inside of the `src/overseer/defaults/models` directory of this repo, and the `demos.yml` file it creates is based on the `demos.example.yml` file in this directory. 

However, before creating any of this, Overseer first checks inside of this `config.example.yml` file for a hidden setting: `paper_release_mode`. To prepare for a release build, the first thing we need to do is add this setting to the `config.example.yml` file, and set it to true:

```yaml
global_settings:
  default_save_dir: .
  default_save_name: figure
  run_on_startup: true
  autosave_axis_settings: false
  paper_release_mode: true # <-- Set this to true 
  anonymous_submission_mode: false
```

If Overseer detects this, it will, instead of creating any new configuration files or models in various places on the user's machine, simply use this file as it's settings file, and use the models folder here as the models. It still creates a new `demos.yml` file based on `demos.example.yml`, but it will do this *inside* of the `src/overseer/defaults` folder instead of somewhere else. 

Thus, to prepare your release build, you need to do the following:
1. Add the `paper_release_mode: true` setting to `src/overseer/defaults/config.example.yml`.
2. Delete the models inside of `src/overseer/defaults/models` that you don't want the user to have access to, and drop your own model inside of here.
3. Edit the `src/overseer/defaults/demos.example.yml` file to only have the demo or demos for your release build. 

After doing this, you can test that everything is working properly by just running Overseer normally (e.g. by running `python3 -m overseer` inside your virtual environment), and making sure that you only see what you want your users to see. If this is the case, you can move on to the next step.

## Creating the Release Build
### Windows
Open up **Powershell** (not cmd!). From the `release/windows/pyinstaller` folder, run the script `build_exe.ps1`. This script requires a single argument, which is the name of your release. So for example:
```
.\build_exe.ps1 CrossDualDynamicRoPReleases
```

After a few minutes, this should complete. In the same folder where you found the script, there should now be a folder called `dist`, inside of which should be a folder of the name you chose. If you look inside of this folder you will find an exe file, which if ran should launch your release build! 

The `_internal` folder here is *essential* to include alongside your exe file. I recommend zipping the folder, and giving it out that way, with instructions to unzip and run the exe. That's it!
### Mac OS
The process is similar to windows in that I provide a script to build your releases using PyInstaller, but there are some additional things to discuss here.

First, the main script you want is `release/macos/dmg_pipeline/build_app.sh`. There is a decent amount more going on in this script than in the Windows, a lot of code commented out, and a part of it which is somewhat optional, so let me go through the code here. 

```sh
#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${1:-}"
DMG_NAME="${1:-}"

if [[ -z "$APP_NAME" ]]; then
  echo "Usage: ./build_app.sh APP_NAME"
  exit 1
fi

cd "$(dirname "$0")"
rm -rf build dist dmgroot "${DMG_NAME}.dmg"

pyinstaller \
  -n "$APP_NAME" \
  --clean \
  --noconfirm \
  --windowed \
  --onedir \
  --icon ../../../src/overseer/assets/icon.icns \
  --additional-hooks-dir=. \
  --collect-data overseer \
  --collect-data scienceplots \
  --add-data "../../../src/overseer/defaults/models:overseer/defaults/models" \
  --collect-all mesa \
  --hidden-import overseer.tools.log_formatter \
  --paths ../../../src \
  ./main.py
```

This here is the part of the script which is identical to the Windows version - it has PyInstaller create a .App file which a normie can drop in their Applications folder, double click on, and be good to go. In the file, there is some extra commented out code here which you would want to fill in if you've paid to register as an Apple Dev and are planning on signing and notarizing a final product. 

However, for MacOS, the standard practice is not just to give the user this .App folder. Instead, they are usually packaged as dmg files. There is some additional code underneath which does this:

```python
mkdir -p dmgroot
cp -R "dist/${APP_NAME}.app" dmgroot/
ln -s /Applications "dmgroot/Applications"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder dmgroot \
  -ov -format UDZO \
  "${DMG_NAME}.dmg"
```

After running the code consisting of these two snippets, which is precisely what will happen if you run `./build_app.sh YourReleaseName`, you will get a dmg file called YourReleaseName, that you can hand to any Mac user, and they should know what to do with it. There are several lines of additional code which are what I would use to sign and notarize the final DMG file, allowing users to run the app without getting any warnings and having to mess around in their settings. 

If you aren't a paying Apple Developer and you don't want the user to have to futz around in their settings, you can advise them to run the following terminal command on their dmg file before clicking on it:

```sh
xattr -dr com.apple.quarantine /path/to/file.dmg
```

So that's another option. 