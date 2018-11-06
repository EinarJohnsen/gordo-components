# -*- coding: utf-8 -*-

import logging
import pydoc
from typing import List, Union
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.base import BaseEstimator


logger = logging.getLogger(__name__)


def pipeline_from_definition(pipe_definition: dict) -> Union[FeatureUnion, Pipeline]:
    """
    Construct a Pipeline or FeatureUnion from a definition.

    Example:
    >>> import yaml
    >>> from gordo_components.pipeline_translator import pipeline_from_definition
    >>> raw_config = '''
    ... sklearn.pipeline.Pipeline:
    ...         steps:
    ...             - sklearn.decomposition.PCA:
    ...                 n_components: 3
    ...             - sklearn.pipeline.FeatureUnion:
    ...                 - sklearn.decomposition.PCA:
    ...                     n_components: 3
    ...                 - sklearn.pipeline.Pipeline:
    ...                     - sklearn.preprocessing.MinMaxScaler
    ...                     - sklearn.decomposition.TruncatedSVD:
    ...                         n_components: 2
    ...             - sklearn.ensemble.RandomForestClassifier:
    ...         max_depth: 3'''
    >>> config = yaml.load(raw_config)
    >>> scikit_learn_pipeline = pipeline_from_definition(config)


    Parameters
    ---------
        pipe_definition: list - List of steps for the Pipeline / FeatureUnion
        constructor_class: object - What to place the list of transformers into,
                                    either sklearn.pipeline.Pipeline/FeatureUnion

    Returns
    -------
        sklearn.pipeline.Pipeline
    """
    return _build_step(pipe_definition)


def _build_branch(definition: List[Union[str, dict]],
                  constructor_class=Union[Pipeline, None]):
    """
    Builds a branch of the tree and optionall constructs the class with the given
    leafs of the branch, if constructor_class is not none. Otherwise just the
    built leafs are returned.
    """
    steps = [(f'step_{i}', _build_step(step)) for i, step in enumerate(definition)]
    return steps if constructor_class is None else constructor_class(steps)


def _build_step(step: dict) -> Union[FeatureUnion, Pipeline, BaseEstimator]:
    """
    Build an isolated step within a transformer list, given a dict config

    Parameters
    ----------
        step: dict/str - A dict, with a single key and associated dict
                         where the associated dict are parameters for the
                         given step.

                         Example: {'sklearn.preprocessing.PCA':
                                        {'n_components': 4}
                                  }
                            Gives:  PCA(n_components=4)

                        Alternatively, 'step' can be a single string, in
                        which case the step will be initiated w/ default
                        params.

                        Example: 'sklearn.preprocessing.PCA'
                            Gives: PCA()
    Returns
    -------
        Scikit-Learn Transformer or BaseEstimator
    """
    logger.debug(f"Building step: {step}")

    # Here, 'step' _should_ be a dict with a single key
    # and an associated dict containing parameters for the desired
    # sklearn step. ie. {'sklearn.preprocessing.PCA': {'n_components': 2}}
    if isinstance(step, dict):
        if len(step.keys()) != 1:
            raise ValueError(f"Step should have a single key, "
                             f"found multiple: {step.keys()}")

        import_str = list(step.keys())[0]
        params = step.get(import_str, dict())

        StepClass = pydoc.locate(import_str)

        # FeatureUnion or another Pipeline transformer
        if any(StepClass == obj for obj in [FeatureUnion, Pipeline]):

            # Need to ensure the parameters to be supplied are valid FeatureUnion
            # & Pipeline both take a list of transformers, but with different
            # kwarg, here we pull out the list to keep _build_branch generic
            if 'transformer_list' in params:
                params['transformer_list'] = _build_branch(params['transformer_list'], None)
            elif 'steps' in params:
                params['steps'] = _build_branch(params['steps'], None)

            # If params is an iterable, is has to be the first argument
            # to the StepClass (FeatureUnion / Pipeline); a list of transformers
            elif any(isinstance(params, obj) for obj in (tuple, list)):
                return StepClass(_build_branch(params, None))
            else:
                raise ValueError(
                    f'Got {StepClass} but the supplied parameters'
                    f'seem invalid: {params}')
        return StepClass(**params)

    # If step is just a string, can initialize it without any params
    # ie. "sklearn.preprocessing.PCA"
    elif isinstance(step, str):
        StepClass = pydoc.locate(step)
        return StepClass()

    else:
        raise ValueError(f"Expected step to be either a string or a dict,"
                         f"found: {type(step)}")