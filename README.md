# mox_proxy

## Overview
This tool acts on directories of Magic: The Gathering card images, typically those downloaded from mpcfill.com. It performs the following tasks:
* Analyzes each card image to determine if the card is a standard art, extended art, or full art.
* Trims the excess "bleed" from each card.
* Ensures all cards are the correct size.
* Places all cards on a 3x3 grid for printing.
* Adds cut lines to the grid.

Additionally, the tool can be configured to:
* Increase the color saturation of the cards, which can help to mitigate some printing issues.
* Increase the brightness of the cards, which may result in more legible foils.

## Usage Guide
I created this tool for my own use and am just sharing it to help other proxy making hobbyists. This tool was not created with public distribution in mind, and has not been optimized for ease of use by those unfamiliar with python. However, it is a simple tool and even those with no Python experience should find it fairly straightforward.

This guide will assume you have no Python experience at all, and are using this tool because you found it on Reddit and just want to make proxies. If that's you, skip the Quick Start section and go to the Walkthrough.

### Quick Start
1. Use python 3.10 or newer
2. Create a new venv and activate it
3. Install the requirements file
4. Create a directory in the same directory as the script. This will hold the cards you want to process.
5. Download your card images from mpcfill.com and move them into the directory.
6. Run proxify.py. Provide the name of the card directory, and a name for the output directory. It will create the directory if it does not exist.
7. Variables for paper size, card size, border thickness, brightness increase, color saturation, cut line color, and cut line thickness are are the top of the script. If you downloaded your card images from somewhere other than mpcfill, such as a custom card editor, you may want to set `FORCE_STANDARD_FRAME_TYPE` to `True`, or it might create an incorrectly sized border.
8. If there are leftover cards (your directory contained something other than a multiple of 9), the cards names will be output at the end of the script run. 

### Basics
* This tool is a script written in Python, a popular programming language. It relies on Pillow, a popular image-processing library for Python.
* You must use this tool through the terminal. On Windows that will be either cmd or Powershell. On Mac, the default is Terminal. If you're on Linux, you probably don't need to be reading this part.

### Walkthrough
Note: I'll assume you're on Windows.

1. Download Python version 3.10 or newer. There are many resources out there to show you how to do this. https://www.python.org/downloads/ is the official source.
2. Once you have Python installed, download the Proxify files from Github. If you're not familiar with how to do that, the easiest way is to click the green "Code" button and the click "Download ZIP". It will download a file called `proxify-main`.
3. Unzip the project directory and move the folder into a location easy to reach with the terminal. On Windows, that will be something like `Local Disk (C:) > Users > <your username>`.
4. Open your terminal and navigate to the project directory. If you don't know how: open the start menu and search for "Windows PowerShell". Open it, and you'll be presented with a black window with a blinking cursor. The text to the left of the cursor indicates which directory you're in. It will likely be `C:\Users<your_username>` Type `ls` to list the files and directories in your current directory. If you placed the project directory here, you should see it listed. Type `cd proxify-main` (or whatever you named it, if you renamed it) to navigate to the  project directory.
5. Once in the project directory, type `python -m venv venv`. This will create a "virtual environment". Once it's created, we need to activate it by typing `\venv\Scripts\activate`.
6. With the virtual environment activated, type `pip install -r requirements.txt`. This will install the libraries required to run the Proxify tool.
7. Now that you have the tool installed, we need some cards to run it on. See the [Getting Card Images](#getting-card-images) section for this. Once you have your card images, create a directory called `input_cards` in the Proxify project directory (it can be named whatever you want). Move your downloaded cards into the directory - you need at least 9. Also create a directory to hold your finished sheets. As an example, we'll use `card_sheets`.
8. In your terminal, type `python proxify.py` to run the tool. When it prompts for the card directory, type `input_cards`. When it asks for the output directory, type `card_sheets`.
9. The program will run, and it may take a while depending on how many cards you have. When it's finished, the print-ready sheets will be in the `card_sheets` directory.

### Configuration
To configure the tool, open the source code in a text editor. If you're on windows, use Notepad. There are a number of variables at the top of the script. They are set with defaults that should work great on MPC Fill images, but tweak them as needed. Some particular options of note:

* `SATURATION_FACTOR` - increases the color saturation of the images.
* `BRIGHTNESS_FACTOR` - increases the overall brightness of images.
* `FORCE_STANDARD_FRAME_TYPE` - if your card images are not from MPC Fill, the detection process may not understand the borders correctly. You can override the detection process by setting this option to `True`. I have found the need to use this when processing custom cards I created.


### Getting Card Images
#### Archidekt
I use Archidekt to create my card lists. I add cards to my "deck", then I use the "Export Deck" feature to get a list. You'll want to set the "Export Type" to `Text` and set the "Export Options" to export in the format `1x Example Card`. Don't use any section headers.

#### MPC Fill
To get the actual card images, I use MPC Fill. Go to https://mpcfill.com and click "Jump into the projecy editor!". Click "Add Cards" and select `Text`. Paste in the  list from Archidekt. Go through and select all the images you want - I recommend using images that are 800 dpi or higher when possible. When you're finished, click "Download" and select `Card Images`.