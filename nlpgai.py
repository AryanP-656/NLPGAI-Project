# -*- coding: utf-8 -*-
"""NLPGAI_Test_new.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/10w5AiYbbsoD8U4CznDxOzUcNd7ahAozQ
"""

# Install required libraries
!pip install stanza conllu

# Download the Hindi UD-HDTB training data
!wget -O hi_hdtb-ud-test.conllu \
    "https://raw.githubusercontent.com/UniversalDependencies/UD_Hindi-HDTB/master/hi_hdtb-ud-test.conllu"

#old
from conllu import parse_incr

# Read and parse the CoNLL-U file
sentences = []
with open('hi_hdtb-ud-test.conllu', 'r', encoding='utf-8') as f:
    sentences = [sent for sent in parse_incr(f)]

# Extract raw sentence text by concatenating token forms
raw_sentences = [" ".join(token['form'] for token in sent) for sent in sentences]
for i, s in enumerate(raw_sentences[:3], 1):
    print(f"Sentence {i}: {s}")

#curr
from conllu import parse_incr

def load_gold(path):
    with open(path, encoding='utf-8') as f:
        return list(parse_incr(f))

gold_test = load_gold('hi_hdtb-ud-test.conllu')
print(f"Loaded {len(gold_test)} test sentences")

!pip install stanza conllu pandas
import stanza
stanza.download('hi')
nlp = stanza.Pipeline('hi', processors='tokenize,pos,lemma,depparse')

import pandas as pd
def parse_to_df(text):
    doc = nlp(text)
    return pd.DataFrame([{
        'id':     w.id,
        'form':   w.text,
        'upos':   w.upos,
        'head':   w.head,
        'deprel': w.deprel,
        'feats':  w.feats or {}
    } for w in doc.sentences[0].words])

!pip install indic-nlp-library

!git clone https://github.com/anoopkunchukuttan/indic_nlp_resources.git
import os
os.environ['INDIC_RESOURCES_PATH'] = '/content/indic_nlp_resources'
!mv /content/indic_nlp_resources/morph /content/morph

from indicnlp.tokenize import indic_tokenize
from indicnlp.morph.unsupervised_morph import UnsupervisedMorphAnalyzer

analyzer = UnsupervisedMorphAnalyzer(lang='hi', add_marker=False)

def custom_morph_split(token):
    morphs = analyzer.morph_analyze(token)
    if morphs == [token]:
        if token.endswith('ती'):
            return [token[:-2], 'ती']
        if token.endswith('ते'):
            return [token[:-2], 'ते']
        if token.endswith('ए'):
            return [token[:-1], 'ए']
        if token.endswith('ं') and len(token) > 2:
            return [token[:-1], 'ं']
    return morphs

sentence = "किताबें पढ़ी जाती हैं।"
tokens = indic_tokenize.trivial_tokenize(sentence, lang='hi')
print("Tokens:", tokens)

for token in tokens:
    split = custom_morph_split(token)
    print(f"{token} -> {split}")

nlp = stanza.Pipeline('hi', processors='tokenize,pos,lemma,depparse')


text = "बिल गेट्स अमेरिका के सबसे अमीर व्यक्ति हैं।"
doc = nlp(text)

# Print each word with its head and dependency relation
print("ID\tWord\tHead\tDepRel\tMorphFeatures")
for sent in doc.sentences:
    for word in sent.words:
        print(f"{word.id}\t{word.text}\t{word.head}\t{word.deprel}\t{word.feats}")

#to understand mistakes

import stanza
stanza.download('hi')
nlp = stanza.Pipeline('hi', processors='tokenize,pos,lemma,depparse')

tests = [
    "रमेश ने महेश को बुलाया।",                     # indirect object (iobj) vs obl
    "राम और श्याम बाजार गए।",                        # coordination & cc
    "जिसने यह काम किया वह दोषी है।"               # relative clause (acl:relcl) vs wrong root
]

for sent in tests:
    print(f"\nSentence: {sent}")
    doc = nlp(sent)
    print("ID  FORM        UPOS    HEAD  DEPREL")
    for w in doc.sentences[0].words:
        print(f"{w.id:<3} {w.text:<10} {w.upos:<7} {w.head:<5} {w.deprel}")

def apply_hindi_rules(df):
    """
    1) Enrich each row with a 'morph' field = list of morphemes from custom_morph_split.
    2) Apply each rule *only* when the token’s morph list matches the pattern.
    """
    # 1) compute splits once
    df['morph'] = df['form'].apply(custom_morph_split)

    for i, row in df.iterrows():
        form, upos, deprel, head, morph = row['form'], row['upos'], row['deprel'], row['head'], row['morph']

        # Rule A: obj→iobj when the model missed a dative object marked by 'को'
        #    only if 'को' was actually split off as a separate morph
        if deprel=='obj' and 'को' in morph:
            df.at[i,'deprel'] = 'iobj'

        # Rule B: coordination of two PROPNs with 'और'
        #    fix only when you actually see the 'और' in the morphs
        if form=='और' and upos=='CCONJ':
            # nothing to change to head here; cc attachments will be handled by UD itself
            df.at[i,'deprel'] = 'cc'
        #    fix the conjunct token that follows 'और'
        if i>0 and df.at[i-1,'form']=='और' and upos=='PROPN':
            df.at[i,'deprel'] = 'conj'
            df.at[i,'head']  = df.at[i-1,'id']  # attach to the first conjunct

        # Rule C: relative clause marker (जो, जिसने) → mark
        #    only if the token *is* one of those relative pronouns
        if upos=='PRON' and form in ('जो','जिसने'):
            # find the verb in the same sentence
            verbs = df[df['upos']=='VERB']
            if not verbs.empty:
                verb_id = int(verbs.iloc[0]['id'])
                df.at[i,'deprel'] = 'mark'
                df.at[i,'head']  = verb_id

        # Rule D: make the copula 'है' the root
        #    only when 'है' appears (and isn't already root)
        if form=='है' and upos=='AUX' and deprel!='root':
            df.at[i,'deprel'] = 'root'
            df.at[i,'head']  = 0

        # Rule E: split‐based particle correction for 'भी'
        #    only if morph splitting actually gave you a standalone 'भी'
        if 'भी' in morph and deprel=='dep':
            df.at[i,'deprel'] = 'advmod'

    # drop the temporary column
    df.drop(columns=['morph'], inplace=True)
    return df

def evaluate(gold_sents, apply_rules=False):
    total_tokens = correct_head = correct_both = 0
    processed, skipped = 0, 0

    for sent in gold_sents:
        text = " ".join(tok['form'] for tok in sent)
        pred = parse_to_df(text)
        # Optionally apply rules
        if apply_rules:
            pred = apply_hindi_rules(pred)

        gold_heads = [tok['head'] for tok in sent]
        pred_heads = pred['head'].tolist()

        if len(gold_heads) != len(pred_heads):
            skipped += 1
            continue

        processed += 1
        gold_deps  = [tok['deprel'] for tok in sent]
        pred_deps  = pred['deprel'].tolist()

        for gh, gd, ph, pd in zip(gold_heads, gold_deps, pred_heads, pred_deps):
            total_tokens += 1
            if gh == ph:
                correct_head += 1
                if gd == pd:
                    correct_both += 1

    print(f"Processed {processed}, Skipped {skipped} of {len(gold_sents)} sentences")
    uas = correct_head/total_tokens if total_tokens else 0
    las = correct_both/total_tokens if total_tokens else 0
    return uas, las

# Run evaluation on the entire test set
uas_base, las_base     = evaluate(gold_test, apply_rules=False)
uas_hybrid, las_hybrid = evaluate(gold_test, apply_rules=True)

print(f"Baseline → UAS: {uas_base:.2%}, LAS: {las_base:.2%}")
print(f"Hybrid   → UAS: {uas_hybrid:.2%}, LAS: {las_hybrid:.2%}")
print(f"ΔUAS: {(uas_hybrid - uas_base):.2%}, ΔLAS: {(las_hybrid - las_base):.2%}")

gold = gold_test[0]                              # first gold UD sentence
text = " ".join(tok['form'] for tok in gold)
print("Text:", text)

df = parse_to_df(text)
print(df[['id','form','head','deprel']])        # should show non-zero heads

!wget -O mr_ufal-ud-test.conllu \
    "https://raw.githubusercontent.com/UniversalDependencies/UD_Marathi-UFAL/master/mr_ufal-ud-test.conllu"

# Load Marathi test data
def load_marathi_gold(path):
    with open(path, encoding='utf-8') as f:
        return list(parse_incr(f))

gold_mr_test = load_marathi_gold('mr_ufal-ud-test.conllu')
print(f"Loaded {len(gold_mr_test)} Marathi test sentences")

stanza.download('mr')  # Marathi models
nlp_mr = stanza.Pipeline('mr', processors='tokenize,pos,lemma,depparse')

# Marathi-specific morphological rules
def marathi_morph_split(token):
    if token.endswith('ला'):
        return [token[:-2], 'ला']  # Dative case
    if token.endswith('ने'):
        return [token[:-2], 'ने']  # Ergative marker
    if token.endswith('त'):
        return [token[:-1], 'त']   # Aspect marker
    return [token]

def compare_parses(sentence, gold_data, nlp):
    # Get Stanza parse
    doc = nlp(sentence)
    stanza_parse = [(w.text, w.head, w.deprel) for w in doc.sentences[0].words]

    # Get gold standard
    gold_parse = [(t['form'], t['head'], t['deprel']) for t in gold_data]

    # Print comparison table
    print(f"\nSentence: {sentence}")
    print(f"{'Token':<15}{'Stanza (Head,Rel)':<25}{'Gold (Head,Rel)'}")
    print("-"*60)
    for (s_tok, s_h, s_r), (g_tok, g_h, g_r) in zip(stanza_parse, gold_parse):
        match = "✅" if (s_h == g_h) and (s_r == g_r) else "❌"
        print(f"{match} {s_tok:<12} ({s_h}, {s_r:<12}) vs ({g_h}, {g_r})")

# Test 1.1
sentence1 = "शिक्षकाने मुलाला शिकवले."
gold1 = [
    {'form': 'शिक्षकाने', 'head': 3, 'deprel': 'nsubj:erg'},
    {'form': 'मुलाला', 'head': 3, 'deprel': 'obj'},
    {'form': 'शिकवले', 'head': 0, 'deprel': 'root'},
    {'form': '.', 'head': 3, 'deprel': 'punct'}
]

# Test 1.2
sentence2 = "रामने पुस्तक वाचले."
gold2 = [
    {'form': 'रामने', 'head': 3, 'deprel': 'nsubj:erg'},
    {'form': 'पुस्तक', 'head': 3, 'deprel': 'obj'},
    {'form': 'वाचले', 'head': 0, 'deprel': 'root'},
    {'form': '.', 'head': 3, 'deprel': 'punct'}
]

# Test 1.3
sentence3 = "मुलांनी खेळ खेळला."
gold3 = [
    {'form': 'मुलांनी', 'head': 3, 'deprel': 'nsubj:erg'},
    {'form': 'खेळ', 'head': 3, 'deprel': 'obj'},
    {'form': 'खेळला', 'head': 0, 'deprel': 'root'},
    {'form': '.', 'head': 3, 'deprel': 'punct'}
]

compare_parses(sentence1, gold1, nlp_mr)
compare_parses(sentence2, gold2, nlp_mr)
compare_parses(sentence3, gold3, nlp_mr)

# Test 2.1
sentence4 = "पुस्तक टेबलावर आहे."
gold4 = [
    {'form': 'पुस्तक', 'head': 4, 'deprel': 'nsubj'},
    {'form': 'टेबल', 'head': 4, 'deprel': 'obl'},
    {'form': 'वर', 'head': 2, 'deprel': 'case'},
    {'form': 'आहे', 'head': 0, 'deprel': 'root'},
    {'form': '.', 'head': 4, 'deprel': 'punct'}
]

# Test 2.2
sentence5 = "मी शाळेत जातो."
gold5 = [
    {'form': 'मी', 'head': 4, 'deprel': 'nsubj'},
    {'form': 'शाळा', 'head': 4, 'deprel': 'obl'},
    {'form': 'त', 'head': 2, 'deprel': 'case'},
    {'form': 'जातो', 'head': 0, 'deprel': 'root'},
    {'form': '.', 'head': 4, 'deprel': 'punct'}
]

# Test 2.3
sentence6 = "पक्षी झाडावर बसले."
gold6 = [
    {'form': 'पक्षी', 'head': 4, 'deprel': 'nsubj'},
    {'form': 'झाड', 'head': 4, 'deprel': 'obl'},
    {'form': 'वर', 'head': 2, 'deprel': 'case'},
    {'form': 'बसले', 'head': 0, 'deprel': 'root'},
    {'form': '.', 'head': 4, 'deprel': 'punct'}
]


compare_parses(sentence4, gold4, nlp_mr)
compare_parses(sentence5, gold5, nlp_mr)
compare_parses(sentence6, gold6, nlp_mr)


sentence = "तो टेबलावर पुस्तक ठेवला ."
gold = [
    {'form': 'तो', 'head': 4, 'deprel': 'nsubj'},
    {'form': 'टेबलावर', 'head': 4, 'deprel': 'obl'},  # 'टेबल' + 'वर'
    {'form': 'पुस्तक', 'head': 4, 'deprel': 'obj'},
    {'form': 'ठेवला', 'head': 0, 'deprel': 'root'},
    {'form': '.', 'head': 4, 'deprel': 'punct'}
]

compare_parses(sentence, gold, nlp_mr)


sentence = "मी जेवण केले नाही ."
gold = [
    {'form': 'मी', 'head': 3, 'deprel': 'nsubj'},
    {'form': 'जेवण', 'head': 3, 'deprel': 'obj'},
    {'form': 'केले', 'head': 0, 'deprel': 'root'},
    {'form': 'नाही', 'head': 3, 'deprel': 'neg'},
    {'form': '.', 'head': 3, 'deprel': 'punct'}
]

compare_parses(sentence, gold, nlp_mr)

def apply_marathi_rules(df):

    # Rule 1: Instrumental case handling
    instr_mask = (df['feats'].str.contains('Case=Ins', na=False))
    df.loc[instr_mask, 'deprel'] = 'obl'

    # Rule 2: Possessive marker attachment
    poss_markers = ['चा', 'चे', 'ची']
    for i, row in df.iterrows():
        if row['form'] in poss_markers and i > 0:
            df.at[i, 'head'] = df.at[i-1, 'id']
            df.at[i, 'deprel'] = 'case'

    return df

def evaluate_marathi(gold_sents, apply_rules=False):
    total = correct_head = correct_rel = 0

    for sent in gold_sents:
        text = " ".join([t['form'] for t in sent])
        doc = nlp_mr(text)

        # Convert to DataFrame
        pred = pd.DataFrame([{
            'id': w.id,
            'form': w.text,
            'head': w.head,
            'deprel': w.deprel,
            'feats': w.feats
        } for w in doc.sentences[0].words])

        if apply_rules:
            pred = apply_marathi_rules(pred)

        # Alignment check
        if len(pred) != len(sent):
            continue

        # Compare with gold
        for gold_tok, pred_row in zip(sent, pred.itertuples()):
            total += 1
            if gold_tok['head'] == pred_row.head:
                correct_head += 1
                if gold_tok['deprel'] == pred_row.deprel:
                    correct_rel += 1

    return correct_head/total, correct_rel/total

# Run evaluation
uas_mr, las_mr = evaluate_marathi(gold_mr_test[:100])  # Test on first 100 sents for speed
print(f"Marathi Baseline: UAS {uas_mr:.2%}, LAS {las_mr:.2%}")

uas_mr_hybrid, las_mr_hybrid = evaluate_marathi(gold_mr_test[:100], apply_rules=True)
print(f"With Rules: UAS {uas_mr_hybrid:.2%}, LAS {las_mr_hybrid:.2%}")

# Test Example 3 with new rules
doc = nlp_mr("तो येत नाही .")
pred = pd.DataFrame([{'form':w.text, 'upos':w.upos, 'id':w.id,
                     'head':w.head, 'deprel':w.deprel, 'feats':w.feats}
                    for w in doc.sentences[0].words])
improved_pred = apply_marathi_rules(pred)

print("Before Rules:".ljust(20), pred[['form', 'head', 'deprel']].values)
print("After Rules:".ljust(20), improved_pred[['form', 'head', 'deprel']].values)

def compute_uas_las(gold_file, pred_file):
    total = 0
    correct_heads = 0
    correct_labels = 0

    with open(gold_file, 'r', encoding='utf-8') as gf, open(pred_file, 'r', encoding='utf-8') as pf:
        gold_lines = gf.readlines()
        pred_lines = pf.readlines()

    for g_line, p_line in zip(gold_lines, pred_lines):
        if g_line.strip() == '' or g_line.startswith('#'):
            continue  # skip sentence separators or comments

        g_fields = g_line.strip().split('\t')
        p_fields = p_line.strip().split('\t')

        if '-' in g_fields[0] or '.' in g_fields[0]:  # skip multiword tokens or ellipsis
            continue

        gold_head = g_fields[6]
        gold_deprel = g_fields[7]

        pred_head = p_fields[6]
        pred_deprel = p_fields[7]

        total += 1
        if gold_head == pred_head:
            correct_heads += 1
            if gold_deprel == pred_deprel:
                correct_labels += 1

    uas = 100 * correct_heads / total
    las = 100 * correct_labels / total
    return uas, las

gold_path = '/path/to/gold.conllu'
pred_path = '/path/to/predicted.conllu'

uas, las = compute_uas_las(gold_path, pred_path)
print(f"UAS: {uas:.2f}%")
print(f"LAS: {las:.2f}%")

def compute_pos_accuracy(gold_file, pred_file):
    total = 0
    correct = 0

    with open(gold_file, 'r', encoding='utf-8') as gf, open(pred_file, 'r', encoding='utf-8') as pf:
        for g_line, p_line in zip(gf, pf):
            if g_line.strip() == '' or g_line.startswith('#'):
                continue

            g_fields = g_line.strip().split('\t')
            p_fields = p_line.strip().split('\t')

            if '-' in g_fields[0] or '.' in g_fields[0]:
                continue

            total += 1
            if g_fields[3] == p_fields[3]:  # UPOS column
                correct += 1

    return 100 * correct / total

pos_acc = compute_pos_accuracy(gold_path, pred_path)
print(f"POS Accuracy: {pos_acc:.2f}%")

def compute_exact_match(gold_file, pred_file):
    with open(gold_file, 'r', encoding='utf-8') as gf, open(pred_file, 'r', encoding='utf-8') as pf:
        gold_sent = []
        pred_sent = []

        exact_match_count = 0
        total_sentences = 0

        for g_line, p_line in zip(gf, pf):
            if g_line.strip() == '' and p_line.strip() == '':
                total_sentences += 1
                if gold_sent == pred_sent:
                    exact_match_count += 1
                gold_sent = []
                pred_sent = []
            else:
                g_fields = g_line.strip().split('\t')
                p_fields = p_line.strip().split('\t')
                if len(g_fields) < 8 or len(p_fields) < 8 or '-' in g_fields[0]:
                    continue
                gold_sent.append((g_fields[6], g_fields[7]))  # HEAD, DEPREL
                pred_sent.append((p_fields[6], p_fields[7]))

        return 100 * exact_match_count / total_sentences

def compute_morph_accuracy(gold_file, pred_file):
    total = 0
    correct = 0

    with open(gold_file, 'r', encoding='utf-8') as gf, open(pred_file, 'r', encoding='utf-8') as pf:
        for g_line, p_line in zip(gf, pf):
            if g_line.strip() == '' or g_line.startswith('#'):
                continue

            g_fields = g_line.strip().split('\t')
            p_fields = p_line.strip().split('\t')

            if len(g_fields) < 6 or len(p_fields) < 6 or '-' in g_fields[0]:
                continue

            total += 1
            if g_fields[5] == p_fields[5]:  # FEATS column
                correct += 1

    return 100 * correct / total

from collections import Counter

def compute_per_label_f1(gold_file, pred_file):
    label_counts = Counter()
    correct_counts = Counter()

    with open(gold_file, 'r') as gf, open(pred_file, 'r') as pf:
        for g_line, p_line in zip(gf, pf):
            if g_line.strip() == '' or g_line.startswith('#'):
                continue

            g_fields = g_line.strip().split('\t')
            p_fields = p_line.strip().split('\t')

            if len(g_fields) < 8 or '-' in g_fields[0]:
                continue

            gold_label = g_fields[7]
            pred_label = p_fields[7]

            label_counts[gold_label] += 1
            if gold_label == pred_label and g_fields[6] == p_fields[6]:
                correct_counts[gold_label] += 1

    for label in label_counts:
        precision = correct_counts[label] / label_counts[label]
        print(f"{label}: Precision = {precision:.2%}")

