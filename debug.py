from typing import Any
from reddwarf.polis import PolisClient
from reddwarf.data_presenter import DataPresenter
import pandas as pd

from reddwarf import utils
import json
import numpy as np


CONVOS = {
    # Topic: What were the most significant developments in tech and politics in 2018?
    # 5 groups, 65 ptpts (56 grouped), 43 comments (open)
    "tech-politics-2018": {
        "report_id": "r2dfw8eambusb8buvecjt",
        "convo_id": "6jrufhr6dp",
    },
    # Topic: How should we operate vehicle-for-hire, e.g. Uber, Lyft and taxis in Toronto?
    # 2 groups, 47 ptpts (36 grouped), 69 comments (open)
    "rideshare-toronto": {
        "report_id": "r8xhmkwp6shm9yfermteh",
        "convo_id": "7vampckwrh",
    },
    # Topic: Help us pick rules for our AI chatbot! 7/7
    # 2 groups, 1_127 ptpts (1_094 grouped), 1_418 comments (closed)
    "anthropic-ccai": {
        "report_id": "r3rwrinr5udrzwkvxtdkj",
        "convo_id": "3akt5cdsfk",
    },
    # Topic: How should we use open source tools in governmment?
    # Test convo using xids and avatar images.
    "xid-testing": {
        "convo_id": "4kjz5rrrfe",
    },
}

if True:
    # testing representativeness calculations
    report_id = CONVOS["tech-politics-2018"]["report_id"]
    print(f"Loading data from report: https://pol.is/report/{report_id}")

    client = PolisClient()
    client.load_data(report_id=report_id)

    # This allows us to skip recalculating clustering, and instead rely on
    # clustering results from polismath's API endpoint. The value of this is
    # being able to compare comment stat calculations even when clustering isn't
    # yet reproducing Polis' exact behavior.
    USE_POLISMATH_CLUSTERING = True
    if USE_POLISMATH_CLUSTERING:
        math_data: Any = client.data_loader.math_data # type:ignore
        all_clustered_participant_ids, cluster_labels = utils.extract_data_from_polismath(math_data)
        # Force same participant subset (Polis has some edge-cases where it
        # keeps participants that would otherwise be cut)
        client.keep_participant_ids = all_clustered_participant_ids

    # Generate vote matrix and run clustering
    vote_matrix = client.get_matrix(is_filtered=True)
    client.run_pca()
    client.scale_projected_data()

    if USE_POLISMATH_CLUSTERING:
        # Fake optimal labels from polismath data.
        client.optimal_cluster_labels = cluster_labels
    else:
        client.find_optimal_k()  # Find optimal number of clusters
        cluster_labels = client.optimal_cluster_labels

    grouped_stats_df = utils.calculate_comment_statistics_by_group(
        vote_matrix=vote_matrix,
        cluster_labels=cluster_labels, # type:ignore
    )
    polis_repness = utils.select_representative_statements(grouped_stats_df=grouped_stats_df)

    print(json.dumps(polis_repness, indent=2))

    presenter = DataPresenter(client=client)
    presenter.render_optimal_cluster_figure()

if False:
    # test agora method
    from reddwarf.agora import run_clustering
    from reddwarf.types.agora import Conversation

    report_id = CONVOS["tech-politics-2018"]["report_id"]
    print(f"Loading data from report: https://pol.is/report/{report_id}")

    client = PolisClient()
    client.load_data(report_id=report_id)

    convo: Conversation = {
        "id": "demo",
        "votes": client.data_loader.votes_data,
    }
    results = run_clustering(conversation=convo)

    from pprint import pprint
    pprint(results)

if False:
    client = PolisClient()
    client.load_data(conversation_id="9xxwa9jpkm")
    # Reproducing this output: https://github.com/compdemocracy/openData/blob/master/london.youth.policing
    # participant-votes.csv matches, but votes.csv is missing entries.
    # BUG: dates for exports seemingly not matching between matrix build and vote export.
    matrix_raw = client.get_matrix(is_filtered=False, cutoff=1658934741418)
    participants_votes_df = client.build_participants_dataframe(matrix_raw)
    print(participants_votes_df)

# This is a sanity-check for equality of a participants-votes.csv dataframe generated from raw votes vs a downloaded export.
if False:
    # Generate the participants-votes dataframe from raw data
    client = PolisClient(is_strict_moderation=True)
    client.load_data(directory_url="https://raw.githubusercontent.com/compdemocracy/openData/refs/heads/master/london.youth.policing/")
    raw_matrix = client.get_matrix(is_filtered=False)
    # Drop statement columns if no votes.
    raw_matrix = raw_matrix.dropna(axis="columns", how="all")
    # Convert all int columns to strings for easier comparison.
    raw_matrix.columns = raw_matrix.columns.astype(str)
    participants_votes_generated = client.build_participants_dataframe(vote_matrix=raw_matrix)
    participants_votes_generated = participants_votes_generated.join(raw_matrix)
    # Remove rows for participants with zero votes.
    non_voting_participant_ids = participants_votes_generated[participants_votes_generated["n_votes"] == 0].index
    participants_votes_generated = participants_votes_generated.drop(index=non_voting_participant_ids)

    # Generate dataframe from downloaded CSV.
    col_mapper = {
        "participant": "participant_id",
        "group-id": "group_id",
        "n-comments": "n_comments",
        "n-votes": "n_votes",
        "n-agree": "n_agree",
        "n-disagree": "n_disagree",
    }
    participants_votes_downloaded = (
        pd
            .read_csv("https://raw.githubusercontent.com/compdemocracy/openData/refs/heads/master/london.youth.policing/participants-votes.csv")
            .rename(columns=col_mapper)
            # Override group_id for now, until we can generate and compare.
            .assign(group_id=None)
            .set_index("participant_id")
            .sort_index()
    )
    is_dataframes_equal = participants_votes_downloaded.equals(participants_votes_generated)
    print(f"downloaded and generated dataframes are equal? {is_dataframes_equal}")
    print(participants_votes_downloaded.shape)
    print(participants_votes_generated.shape)
    print(participants_votes_downloaded.compare(participants_votes_generated))
