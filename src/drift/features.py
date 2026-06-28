import json
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

def parse_embeddings(df: pd.DataFrame) -> np.ndarray:
    '''
    Parse JSON embeddings into numpy array.

    Parameter:
    - df: DataFrame with 'embedding_json' column
    Returns:
    - np.ndarry of shape (num_samples, embedding_dim)
    '''
    embeddings = df['embedding_json'].dropna().apply(json.loads).tolist()
    return np.array(embeddings)

def compute_text_features(df: pd.DataFrame) -> pd.DataFrame:
    '''
    Compute text-based features like input length.
    
    Parameter:
    - df: DataFrame with 'input_data' column
    Returns:
    - DataFrame with new feature columns
    '''
    texts = df['input_data'].apply(lambda x: json.loads(x)['text'])

    # normalize to string
    texts = texts.apply(lambda t: t if isinstance(t, str) else ' '.join(t))
    
    df_features = pd.DataFrame()
    df_features['input_length'] = df["input_length"]

    df_features['word_count'] = texts.apply(lambda x: len(x.split()))

    df_features['special_char_ratio'] = texts.apply(
        lambda x: sum(not c.isalnum() for c in x) / max(len(x), 1)
    )
    
    return df_features


def reduce_dimensionality(embeddings: np.ndarray, n_components: int = 10) -> PCA:
    '''
    Reduce embedding dimensionality using PCA.
    
    Parameters:
    - embeddings: np.ndarray of shape (num_samples, embedding_dim)
    - n_components: target dimensionality

    Returns:
    - np.ndarray of shape (num_samples, n_components)
    '''
    n_samples, n_features = embeddings.shape
    
    if n_samples < 2:
        raise ValueError("Not enough samples for PCA")
    
    # enforce PCA constraint
    n_components = min(n_components, n_samples, n_features)
    
    pca = PCA(n_components=n_components)
    reduced = pca.fit(embeddings)
    return reduced

def transform_features(pca: PCA, embeddings: np.ndarray):
    '''
    Transform embeddings using fitted PCA model.
    
    Parameters:
    - pca: fitted PCA model
    - embeddings: np.ndarray of shape (num_samples, embedding_dim)
    Returns:
    - np.ndarray of shape (num_samples, n_components)
    '''
    return pca.transform(embeddings)

def build_feature_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    '''
    Build a feature DataFrame combining text features and reduced embeddings.
    
    Parameter:
    - df: DataFrame with raw data and 'embedding_json' column

    Returns:
    - DataFrame with combined features
    '''
    if df.empty:
        raise ValueError("No data available for given time window")
    embeddings = parse_embeddings(df)
    pca = reduce_dimensionality(embeddings)
    reduced_embeddings = transform_features(pca, embeddings)

    emb_df = pd.DataFrame(
        reduced_embeddings,
        columns = [f"pca_{i}" for i in range(reduced_embeddings.shape[1])]
    )

    # text features
    text_df = compute_text_features(df)

    # combine
    final_df = pd.concat([emb_df, text_df], axis=1)

    return final_df