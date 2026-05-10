![Demo](src/modeling_tools/assets/demo.gif)

# Overseer
Overseer is a model visualization and exploration toolkit. It was developed for the following two purposes:
1. To minimize the friction between creating computational models of all kinds and exploring the results of those models. 
2. To allow for the creation of publication level figures without having to spend hours remembering matplotlib commands (and even when you do know the commands, it is still a drag). 

The primary inspiration for this project is [Desmos](https://www.desmos.com/). Desmos is an incredible tool which allows for exploration, but the web interface is limited, as its ability to have figures exported for publication. More importantly, Desmos limits the user to the graphing of analytical functions. 

Overseer can be effectively summed up as an answer the question: what if Desmos, but Turing complete? 

Want to numerically simulate partial differential equations? Running some agent-based simulations?  Build an interface for analyzing a big dataset? Regardless of your use-case, Overseer will allow you to quickly explore whatever you're building. 

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