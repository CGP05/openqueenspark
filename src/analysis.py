import re
import itertools
from collections import defaultdict
from heapq import nlargest
from operator import itemgetter
from wordcloud import WordCloud
import io

STOPWORDS = frozenset([
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself",
    "she", "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
    "theirs", "themselves", "what", "which", "who", "whom", "this", "that", "these",
    "those", "am", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "having", "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if",
    "or", "because", "as", "until", "while", "of", "at", "by", "for", "with", "about",
    "against", "between", "into", "through", "during", "before", "after", "above",
    "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where", "why", "how",
    "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can",
    "will", "just", "don", "should", "now", "it's", "we're", "we'll", "they're", "can't",
    "won't", "isn't", "don't", "he's", "she's", "i'm", "aren't", "government", "house",
    "committee", "would", "speaker", "motion", "mr", "mrs", "ms", "member", "minister",
    "canada", "members", "time", "prime", "one", "parliament", "us", "bill", "act",
    "like", "canadians", "people", "said", "want", "could", "issue", "today", "hon",
    "order", "party", "canadian", "think", "also", "new", "get", "many", "say", "look",
    "country", "legislation", "law", "department", "two", "day", "days", "madam", "must",
    "that's", "okay", "thank", "really", "much", "there's", "yes", "no", "ontario",
    "mpp", "assembly", "legislative", "province", "provincial", "premier", "queenvs",
    "park", "queens"
])

r_punctuation = re.compile(r"[^\s\w0-9'’—-]", re.UNICODE)
r_whitespace = re.compile(r'[\s—]+')

def text_token_iterator(text):
    text = r_punctuation.sub('', text.lower())
    for word in r_whitespace.split(text):
        if word and len(word) > 2 and word not in STOPWORDS:
            yield word

def ngram_iterator(tokens, n=2):
    """
    Custom tokenization logic (ngram_iterator) to produce daily n-grams.
    Uses itertools.tee to create sliding window over token iterator.
    """
    sub_iterators = itertools.tee(tokens, n)
    for i, iterator in enumerate(sub_iterators[1:]):
        for x in range(i + 1):
            next(iterator, None)
    for words in zip(*sub_iterators):
        yield ' '.join(words)

class FrequencyModel(dict):
    """
    Maps n-grams to relative frequency within a text corpus.
    """
    def __init__(self, items, min_count=1):
        counts = defaultdict(int)
        total_count = 0
        for item in items:
            counts[item] += 1
            total_count += 1
        self.count = total_count
        total_count = float(total_count) if total_count > 0 else 1.0
        self.update(
            (k, v / total_count) for k, v in counts.items() if v >= min_count
        )

    def most_common(self, n=10):
        return nlargest(n, iter(self.items()), key=itemgetter(1))

def analyze_speeches(speech_records):
    """
    Analyzes daily speeches using custom tokenization and ngram_iterator.
    Returns:
        dict with:
            - word_of_the_day: str
            - top_ngrams: list of dicts [{'text': ..., 'score': ...}]
            - full_text: str (for wordcloud generation)
    """
    combined_text = " ".join([s['text'] for s in speech_records if s.get('text')])
    if not combined_text.strip():
        return {
            'word_of_the_day': 'N/A',
            'top_ngrams': [],
            'full_text': ''
        }

    # Generate 1-grams, 2-grams, 3-grams
    tokens_list = list(text_token_iterator(combined_text))

    unigram_model = FrequencyModel(tokens_list, min_count=2)
    bigram_model = FrequencyModel(ngram_iterator(iter(tokens_list), n=2), min_count=2)
    trigram_model = FrequencyModel(ngram_iterator(iter(tokens_list), n=3), min_count=2)

    top_unigrams = unigram_model.most_common(10)
    top_bigrams = bigram_model.most_common(10)
    top_trigrams = trigram_model.most_common(10)

    top_ngrams = []
    for word, freq in top_trigrams[:3]:
        top_ngrams.append({'text': word, 'score': round(freq * 1000, 2), 'type': 'trigram'})
    for word, freq in top_bigrams[:5]:
        top_ngrams.append({'text': word, 'score': round(freq * 1000, 2), 'type': 'bigram'})
    for word, freq in top_unigrams[:10]:
        top_ngrams.append({'text': word, 'score': round(freq * 1000, 2), 'type': 'unigram'})

    # Word of the Day selection (prefer top bigram or unigram with highest distinctiveness)
    word_of_the_day = "Ontario Discourse"
    if top_bigrams:
        word_of_the_day = top_bigrams[0][0].title()
    elif top_unigrams:
        word_of_the_day = top_unigrams[0][0].title()

    return {
        'word_of_the_day': word_of_the_day,
        'top_ngrams': top_ngrams,
        'full_text': combined_text
    }

def generate_wordcloud_image(text, width=800, height=400):
    """
    Generates a WordCloud PIL image / bytes buffer.
    """
    wc = WordCloud(
        width=width,
        height=height,
        background_color="white",
        stopwords=STOPWORDS,
        colormap="Blues",
        max_words=100
    ).generate(text if text.strip() else "Ontario Legislature Hansard Proceedings")

    img_buffer = io.BytesIO()
    wc.to_image().save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer
