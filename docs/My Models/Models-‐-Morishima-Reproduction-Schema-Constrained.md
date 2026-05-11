This one is just a little thing I made. It implements the [Morishima Reinvestment Model](https://github.com/alexbcreiner0/Disequilibrium-Linear-Production-Model/wiki/Models%E2%80%90Morishima-Disproportionality-Reinvestment-Model) but via direct step-based linear simulation instead of using the closed form solution equations as that one does. Since it is actually simulated, we can implement some things which Morishima mentions in Marx's Economics like disallowing negative output values as well as creating a fixed-size work force and implementing an full-employment ceiling (hence the name for this).

Additionally, I added a couple of extra little features concerning the workforce:

- The work force is constantly growing at a rate r times the current level of employment.
- The work force is constantly shrinking at a rate of s times the current level of unemployment.

Thus the work force can grow if workers are being consistently employed, but will decay due to starvation and exposure if the unemployment is high. It is interesting to experiment and see just how irresponsible the system can get away with being before there is population collapse.