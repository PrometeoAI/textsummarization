import spacy
import argparse
import numpy as np
from collections import Counter
import datetime

start_time = datetime.datetime.now()
parser = argparse.ArgumentParser()

#To run spacy, in command line: pip install spacy
#python -m spacy download en

# nlp = spacy.load('en', disable=['parser', 'tagger', 'ner', 'textcat', 'tokenizer'])
nlp = spacy.load('en')
nlp.add_pipe(nlp.create_pipe('sentencizer'))

parser.add_argument('--test_file', type=str, required=True, dest = 'test_file')
parser.add_argument('--pred_file', type=str, required=True, dest = 'output_file')
parser.add_argument('--summary_length', type=int, required=True, dest = 'summary_length')
parser.add_argument('--events', type=str, required=True, dest = 'events')
parser.add_argument('--activities', type=str, required=True, dest = 'activities')

args = parser.parse_args()

summary_length = args.summary_length


def generate_actions_nouns(events = args.events, activities = args.events):

    event_hyponyms_file = 'event_hyponyms.txt'
    activity_hyponyms_file = 'activity_hyponyms.txt'

    f_events = open(event_hyponyms_file, 'r')
    event_hyponyms = set([line.rstrip('\n').lower() for line in f_events])
    f_activities = open(activity_hyponyms_file, 'r')
    activity_hyponyms = set([line.rstrip('\n').lower() for line in f_activities])

    action_nouns = event_hyponyms.union(activity_hyponyms)

    return action_nouns

def get_character_positions(ent1, ent2):
    #works both for tokens and spans (spacy classes)
    ent1 = sentence_entities[i]
    ent2 = sentence_entities[i+1]
    if type(ent1) == spacy.tokens.token.Token:
        A1 = int(ent1.idx)
        A2 = int(ent1.idx)+int(len(ent1))
    else:
        A1 = int(ent1.start_char)
        A2 = int(ent1.end_char)

    if type(ent2) == spacy.tokens.token.Token:
        B1 = int(ent2.idx)
        B2 = int(ent2.idx)+int(len(ent2))
    else:
        B1 = int(ent2.start_char)
        B2 = int(ent2.end_char)

    return A1, A2, B1, B2

action_nouns = generate_actions_nouns()


with open(args.test_file, "r") as f:
	data = f.read()

#WE ARE ONLY USING THE FIRST 1000 ARTICLES - WITH 1000 ARTICLES, IT RUNS IN 4 MINUTES.
# number_articles = 1000
# articles = data.split("\n")[:number_articles]
articles = data.split("\n")
number_articles = len(articles)
y_pred = []
y_pred_2 = []
sentence_num = 0

all_scores = []

all_sentences = []

all_articles = []

counter_article = 0

entity_score_extension = []
for article in articles:
    counter_article += 1
    print(counter_article)
    doc = nlp(article)

    #FIND TOP 10 NOUNS FOR THIS ARTICLE
    cnt = Counter()
    for tok in doc:
        if tok.pos_ == 'NOUN':
            cnt[tok] += 1

    top10_dict = dict(cnt.most_common(10))
    top10_list = list(top10_dict.keys())

    sentences = list(doc.sents)

    article_matrix = []
    relations_dic = {}
    relation_connector_matrix = []

    atomic_events_dict = {}

    atomic_events_per_article = {} # JUST ADDED
    atomic_event_index = 0 # JUST ADDED
    connector_dict = {}
    relation_dict = {}
    connector_count = 0
    relation_count = 0

    connector_relation_pairs = []

    for sentence in sentences:
        sentence_matrix = []
        sentence_atomic_events = []

        sentence = str(sentence)
        spacy_sentence = nlp(sentence)
        entities_list = list(spacy_sentence.ents)
        
        #make list of both entities and top 10 nouns
        full_entities_list = entities_list + top10_list
        full_entities_string = [str(ent) for ent in full_entities_list]

        #GETS THE ENTITIES AND TOP 10 NOUNS IN THE ORDER IN WHICH THEY APPEAR (ESSENTIAL FOR NEXT STEP)
        full_entities_ordered_list = [ent for ent in full_entities_list if str(ent) in sentence]

        #RENAME AND COUNT
        sentence_entities = full_entities_ordered_list
        entities_count = len(full_entities_ordered_list)

        if entities_count >= 2:
            # for every consecutive pair of entities, we get the pair (atomic candidate) and the connector
            for i in range(entities_count-1):
                ent1 = sentence_entities[i]
                ent2 = sentence_entities[i+1]
                A1, A2, B1, B2 = get_character_positions(ent1, ent2)

                relation = (ent1, ent2)

                #CREATE A DICTIONARY AND A RELATION-CONNECTOR MATRIX
                if relation not in relations_dic.keys():
                    relations_dic[relation] = 1
                else:
                    relations_dic[relation] += 1
                
                atomic_candidate = sentence[A1:B2]
                connector = sentence[A2:B1]

                # check whether connector has verbs
                spacy_connector = nlp(connector)
                connector_has_verb = False
                for token in spacy_connector:
                    if token.pos_ == 'VERB' or (token.pos_ == 'NOUN' and str(token).lower() in action_nouns):
                        connector_has_verb = True
                        break

                #CONDITION TO DETERMINE IF ATOMIC CANDIDATE IS ATOMIC EVENT
                connector_relation_pair = []
                if connector_has_verb:
                    sentence_atomic_events.append(atomic_candidate)
                    if connector not in connector_dict.keys():
                        connector_dict[connector] = connector_count
                        connector_count += 1
                    if relation not in relation_dict.keys():
                        relation_dict[relation] = relation_count
                        relation_count += 1
                    atomic_events_dict[atomic_candidate] = (connector_dict[connector],relation_dict[relation])
                    connector_relation_pair.append((connector,relation))
                    connector_relation_pairs.append(connector_relation_pair)


                    if atomic_candidate not in atomic_events_per_article.keys():
                        atomic_events_per_article[atomic_candidate] = atomic_event_index
                        atomic_event_index += 1

        sentence_matrix = [int(ae in sentence_atomic_events) for ae in atomic_events_per_article.keys()]
        article_matrix.append(sentence_matrix)
        all_sentences.append(sentence)
        all_articles.append(counter_article)
        sentence_num += 1

    #GENERATE SENTENCE TIMES WEIGHTED ATOMIC EVENT MATRIX

    connector_relation_matrix = np.zeros((len(connector_dict),len(relation_dict)))

    for element in connector_relation_pairs:
        connector_relation_matrix[connector_dict[element[0][0]]][relation_dict[element[0][1]]] += 1


    vector = np.sum(connector_relation_matrix, axis =1)
    norm = np.reshape(vector,(len(vector),1))


    connector_relation_matrix = np.transpose(np.transpose(connector_relation_matrix)/vector)

    sentence_row_size = [len(article) for article in article_matrix]
    max_row_size = np.max(sentence_row_size)

    #make all vectors in article_matrix of equal length
    for i in range(len(article_matrix)):
        length = len(article_matrix[i])
        while length < max_row_size:
            article_matrix[i].append(0)
            length += 1


    #NORMALIZE COUNT OF RELATIONS
    A = np.array(list(relations_dic.values()))
    B = 1.0*np.sum(np.array(list(relations_dic.values())))
    normalised_relations_array = A/B


    article_matrix = np.array(article_matrix)
    sentence_scores = []
    for i in range(len(article_matrix)):
        temp_sum = 0
        for j in range(len(article_matrix[i])):
            for key in atomic_events_per_article.keys():
                if atomic_events_per_article[key] == j:
                    current_atomic_candidate = key
                    break
            index_1 = atomic_events_dict[current_atomic_candidate][0]
            index_2 = atomic_events_dict[current_atomic_candidate][1]
            mat = connector_relation_matrix[index_1][index_2]
            temp_sum += article_matrix[i][j]*mat

        sentence_scores.append(temp_sum)

    

    #print('sentence_scores')
    #print(sentence_scores)
    all_scores += sentence_scores

    sentence_scores = np.array(sentence_scores)

    sorted_index_sentences = sentence_scores.argsort()[-summary_length:]

    for k in range(len(sentence_scores)):
        if k in sorted_index_sentences:
            entity_score_extension.append([counter_article,sentences[k],1])
        else:
            entity_score_extension.append([counter_article,sentences[k],0])



    article_summary_2 = ""
    for i in range(summary_length):
        article_summary_2 += str(sentences[sorted_index_sentences[i]])
    y_pred_2.append(article_summary_2)


with open(args.output_file,"w") as f:
	for line in y_pred_2:
		f.write(line)
		f.write("\n")


end_time = datetime.datetime.now()
total_time = end_time - start_time

# with open("entity_score_ranks_test.txt","w") as f:
#     for line in entity_score_extension:
#         f.write(str(line[0]) + " @@@ " + str(line[1]) + " @@@ " + str(line[2]))
#         f.write("\n")

with open("entity_scores_test.txt","w") as f:
    for article, line, sentence in zip(all_articles,all_scores,all_sentences):
        f.write(str(int(article)) + " @@@ " + str(line) + " @@@ " + str(sentence))
        f.write("\n")

print('total running time for '+str(number_articles)+" articles is "+str(total_time))


