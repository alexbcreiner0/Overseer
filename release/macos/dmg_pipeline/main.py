from overseer.__main__ import main
from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()  # pyinstaller documentation says this is necessary, without it the the app just keeps opening copies of itself
    main()
