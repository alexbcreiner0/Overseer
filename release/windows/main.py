# py2app prefers a script to point at as opposed to a package
from overseer.__main__ import main
from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    main()
