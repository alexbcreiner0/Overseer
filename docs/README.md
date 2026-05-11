![Demo](src/modeling_tools/assets/demo.gif)

# Overseer
Overseer is a model visualization and exploration toolkit. It was developed for the following two purposes:
1. To minimize the friction between creating computational models of all kinds and exploring the results of those models. 
2. To allow for the creation of publication level figures without having to spend hours remembering matplotlib commands (and even when you do know the commands, it is still a drag).

The primary inspiration for this project is [Desmos](https://www.desmos.com/). Desmos is an incredible tool which allows for exploration, but the web interface is limited, as its ability to have figures exported for publication. More importantly, Desmos limits the user to the graphing of analytical functions. 

Overseer can be effectively summed up as an answer the question: what if Desmos, but Turing complete? 

Want to numerically simulate partial differential equations? Running some agent-based simulations?  Build an interface for analyzing a big dataset? Regardless of your use-case, Overseer will allow you to quickly explore whatever you're building. 

In addition to points 1 and 2 above, Overseer allows you to create your own 'release mode' versions of particular models, that you can package with papers for publication and allow your readers to explore your models for themselves. See the section on [packaging your own releases](docs/Packaging Your Own Releases) for more on this.

# Installation
There are two demographics of users for Overseer, and two methods of installation depending on which demographic you fall into.  
## Demo Releases for Accompanying Papers
If you are just trying to use the accompanying software to one of my papers, special releases are available for you which can be simply downloaded and ran to display the relevant model**. These are different from the [studio releases]() in that they do not assume that the user has Python installed already.

If you are trying to simply download and play around with the models relating to one of my papers, click the appropriate link below. If you are interested in interacting directly with the tools yourself, making alterations, and building your own models, see the instructions below that.

- [For my upcoming paper titled 'Empirical Redemption of Marx's Law of the Tendential Fall in the Rate of Profit Within Dynamic Cross-Dual Disequilibrium Models, click here](https://github.com/alexbcreiner0/Modeling-Tools/releases/tag/v1.0.0)
   - [The paper (currently in pre-publishing](https://www.alexcreiner.com/documents/rate-of-profit-paper.pdf)

## Main Studio Releases
[See the latest releases page for installation instructions](https://github.com/alexbcreiner0/Modeling-Tools/releases).

## Running Locally
If you don't want to go with the official release route, it's easy to run the project directly:
- Install [https://www.python.org/](Python) if you don't have it, make sure you check the 'add to system path' checkbox in the process if you are a Windows user.
- Clone the repo onto your computer (either by opening up a terminal and typing `git clone https://github.com/alexbcreiner0/Overseer.git` (must have git installed) or by downloading and extract the zip folder (found by clicking the green code button))
- Open up a terminal, navigate inside the folder to the folder:
```
cd Overseer
```
- (Optional but recommended) Create and enter a virtual environment:
```
python -m venv overseer_venv
source overseer_venv/bin/activate
```
- Install the package:
```
pip install .
```
- Then run the package
```
python -m overseer
```