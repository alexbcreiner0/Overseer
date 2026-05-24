![Demo](src/modeling_tools/assets/demo.gif)

# Overseer (Formerly Dr. Creiner's Modelling Tools)

Overseer is a model visualization and exploration toolkit. It aims to make it easy and frictionless to not just build computer models of all kinds, but also engage with them dialectically. Create Desmos-style interfaces quickly and easily for models of all kinds. Simulation PDE's? Running agent-based simulation? No problem! All you need to do is declare your system parameters, make a single Python function which executes the simulation and returns a dictionary of the plots you want to display, and write up a small yaml file declaring the controls you want to have. The tools will handle the rest and create a display of all of your plots so that you can edit your parameters and view the results in real time. 

# Installation
This software was primarily developed for the visualization of a few specific models which I am currently writing papers for. If you are just trying to use the accompanying software to those papers, special releases are available for you which can be simply downloaded and ran to display the relevant model. Just click the appropriate link in the section directly below this one. If you are interested in interacting directly with the tools yourself and making alterations or building your own models, see the instructions below that.

## Special Releases for Accompanying Papers

- [For my upcoming paper titled 'Empirical Redemption of Marx's Law of the TEndential Fall in the Rate of Profit Within Dynamic Cross-Dual Disequilibrium Models, click here](https://github.com/alexbcreiner0/Modeling-Tools/releases/tag/v1.0.0)
   - [The paper (currently in pre-publishing](https://www.alexcreiner.com/documents/rate-of-profit-paper.pdf)
 
## General Releases
[See the latest releases page for instructions](https://github.com/alexbcreiner0/Modeling-Tools/releases).

## Running Locally
If you don't want to go with the official release route, it's easy to run the project directly:
- Install [https://www.python.org/](Python) if you don't have it, make sure you check the 'add to system path' checkbox in the process if you are a Windows user.
- Clone the repo onto your computer (either by opening up a terminal and typing `git clone https://github.com/alexbcreiner0/Modeling-Tools.git` (must have git installed) or by downloading and extract the zip folder (found by clicking the green code button))
- Open up a terminal, navigate inside the folder to the folder:
```
cd Modeling-Tools
```
- (Optional but recommended) Create and enter a virtual environment:
```
python -m venv modeling_tools_venv
source venv/bin/activate
```
- Install the package:
```
pip install -e .
```
- Then run the package
```
python -m modeling_tools
```

## User Guide and Model Documentation
The fastest way to get started using Overseer is to go through the [quick-start tutorial](https://github.com/alexbcreiner0/Overseer/blob/main/docs/1%20-%20Quick-Start%20Tutorial%20--%20Building%20a%20Model%20From%20Scratch.md). Along with that guide, extensive documentation of all of Overseer's features is available here in the docs folder. An organized table of contents is presented in the wiki as well as here:

[1 - Quick-Start Tutorial: Building a Model from Scratch](https://github.com/alexbcreiner0/Overseer/blob/main/docs/1%20-%20Quick-Start%20Tutorial%20--%20Building%20a%20Model%20From%20Scratch.md)

[2 - Controls and Keybindings](https://github.com/alexbcreiner0/Overseer/blob/main/docs/2%20-%20Controls%20and%20Keybindings.md)

[3 - Anatomy of Overseer: The Control and Graph Panels](https://github.com/alexbcreiner0/Overseer/blob/main/docs/3%20-%20Anatomy%20of%20Overseer%20-%20The%20Control%20and%20Graph%20Panels.md)

[4 - Demos and Models](https://github.com/alexbcreiner0/Overseer/blob/main/docs/4%20-%20Demos%2C%20Models%20and%20User%20Data.md)

[5 - Parameters and Presets](https://github.com/alexbcreiner0/Overseer/blob/main/docs/5%20-%20Parameters%20and%20Presets.md)

[6 - Writing Simulations](https://github.com/alexbcreiner0/Overseer/blob/main/docs/6%20-%20Writing%20Simulations.md)

[7 - Plots and Categories](https://github.com/alexbcreiner0/Overseer/blob/main/docs/7%20-%20Plots%20and%20Categories.md)

[8 - Control Panel Widgets](https://github.com/alexbcreiner0/Overseer/blob/main/docs/8%20-%20Control%20Panel%20Widgets.md)

[9 - Saving Pictures, Presets and Data](https://github.com/alexbcreiner0/Overseer/blob/main/docs/9%20-%20Saving%20Pictures%2C%20Presets%2C%20and%20Data.md)

[10 - The Logger and You](https://github.com/alexbcreiner0/Overseer/blob/main/docs/10%20-%20The%20Logger%20and%20You.md)

[11 - Feature Model Releases for Publication and Education](https://github.com/alexbcreiner0/Overseer/blob/main/docs/11%20-%20Feature%20Model%20Releases%20(for%20Publication).md)

[12 - Internal Operation and Efficiency](https://github.com/alexbcreiner0/Overseer/blob/main/docs/12%20-%20Internal%20Operation%20and%20Efficiency.md)

[FAQ](https://github.com/alexbcreiner0/Overseer/blob/main/docs/FAQ.md)

# Documentation On My Included Models
The example models are not just samples of how to use Overseer. They are simulations I have developed for my own research and put a significant amount of work into. I like to be transparent with my research, so all of the models I develop will be open source and included when you download Overseer. Here is some additional documentation on the included models (not finished currently).

[About My Models](https://github.com/alexbcreiner0/Overseer/blob/main/docs/My%20Models/About%20My%20Models.md)

[Wright's Cross-Dual Disequilibrium Model](https://github.com/alexbcreiner0/Overseer/blob/main/docs/My%20Models/Models-%E2%80%90-Wright's-Cross%E2%80%90Dual-Disequilibrium-Model-(Three-Commodity).md)

[Morishima's Reinvestment Schema Model](https://github.com/alexbcreiner0/Overseer/blob/main/docs/My%20Models/Models-%E2%80%90-Morishima's-Reinvestment-Schema-Model.md)
