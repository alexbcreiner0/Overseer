# generate_commodity_nouns.py

from nltk.corpus import wordnet as wn
from wordfreq import zipf_frequency
import inflect

p = inflect.engine()

OUTPUT_FILE = "assets/commodities.txt"

ALLOWED_LEXNAMES = {
    "noun.artifact",
    "noun.substance",
    "noun.food",
    # "noun.plant",
    # "noun.animal",
}

MIN_LEN = 4
MAX_LEN = 14
MIN_ZIPF = 3.2     # tune: higher → more common only

physical_root = wn.synset("physical_entity.n.01")

def is_physical(syn):
    return physical_root in syn.closure(lambda s: s.hypernyms())

def is_good_word(w):
    w = w.lower()
    if len(w) < MIN_LEN or len(w) > MAX_LEN:
        return False
    if not w.isalpha():
        return False
    if not any(ch in "aeiou" for ch in w):
        return False
    if zipf_frequency(w, "en") < MIN_ZIPF:
        return False
    return True

def main():
    words = set()

    for syn in wn.all_synsets('n'):
        if syn.lexname() not in ALLOWED_LEXNAMES:
            continue
        # if not is_physical(syn):
        #     continue

        for lemma in syn.lemma_names():
            w = lemma.replace("_", " ")

            # normalize: remove spaces for tests, but keep them in output if desired
            if not is_good_word(w.replace(" ", "")):
                continue

            plural = p.plural(w).title()
            words.add(plural)

    words = sorted(words)

    with open(OUTPUT_FILE, "w") as f:
        for w in words:
            f.write(w + "\n")

    print(f"Saved {len(words)} plural commodity nouns to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
