import json
import os
import pickle
import sys

import nltk
import numpy as np
import pytest
from nltk import pathsec
from nltk.classify.maxent import load_maxent_params, save_maxent_params
from nltk.parse import DependencyGraph
from nltk.parse.transitionparser import TransitionParser
from nltk.tag.perceptron import AveragedPerceptron, PerceptronTagger

APIS = (
    "averaged_save",
    "averaged_load",
    "tagger_save",
    "maxent_save",
    "transition_train",
    "transition_parse",
)


@pytest.fixture
def roots(tmp_path, monkeypatch):
    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    monkeypatch.setattr(nltk.data, "path", [str(allowed)])
    monkeypatch.setenv("NLTK_DATA", str(allowed))
    monkeypatch.setattr(pathsec, "ENFORCE", True)
    monkeypatch.setattr(pathsec, "_ALLOWED_ROOTS_CACHE", None)
    monkeypatch.setattr(pathsec, "_LAST_DATA_PATHS", None)
    return allowed, outside


def target_path(api, directory):
    return directory / (
        "model" if api in ("tagger_save", "maxent_save") else "model.dat"
    )


def prime(api, path):
    if api == "averaged_load":
        path.write_text(json.dumps({"bias": {"TAG": 1.0}}), encoding="utf8")
    elif api == "transition_parse":
        path.write_bytes(pickle.dumps({}))


def exercise(api, path):
    if api == "averaged_save":
        model = AveragedPerceptron()
        model.weights = {"bias": {"TAG": 1.0}}
        model.save(str(path))
        assert json.loads(path.read_text()) == model.weights
    elif api == "averaged_load":
        model = AveragedPerceptron()
        model.load(str(path))
        assert model.weights == {"bias": {"TAG": 1.0}}
    elif api == "tagger_save":
        PerceptronTagger(load=False).save_to_json(lang="test", loc=str(path))
        assert len(list(path.glob("*.json"))) == 3
    elif api == "maxent_save":
        save_maxent_params(
            np.array([1.0]),
            {("f", "v", "TAG"): 0},
            ["TAG"],
            {"TAG": 0},
            tab_dir=str(path),
        )
        assert len(list(path.iterdir())) == 4
    elif api == "transition_train":
        graph = DependencyGraph(
            "I\tPRP\t2\tnsubj\nsaw\tVBD\t0\tROOT\n"
            "her\tPRP\t2\tdobj\n.\t.\t2\tpunct\n"
        )
        parser = TransitionParser(TransitionParser.ARC_STANDARD)
        parser.train([graph], str(path), verbose=False)
        assert path.stat().st_size > 0
    elif api == "transition_parse":
        assert (
            TransitionParser(TransitionParser.ARC_STANDARD).parse([], str(path)) == []
        )
    else:
        raise AssertionError(api)


def outside_reference(mode, allowed, outside):
    if mode == "absolute":
        return outside
    if mode == "traversal":
        return allowed / ".." / "outside"
    if mode == "symlink":
        link = allowed / "link"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError as error:
            pytest.skip(f"Directory symlinks unavailable: {error}")
        return link
    if mode == "junction":
        if sys.platform == "win32":
            import _winapi

            link = allowed / "junction"
            _winapi.CreateJunction(str(outside), str(link))
            assert link.resolve() == outside.resolve()
            return link
        pytest.skip("Windows directory junction case")
    raise AssertionError(mode)


@pytest.mark.parametrize("api", APIS)
def test_allowed_model_io_still_works(api, roots):
    allowed, _ = roots
    path = target_path(api, allowed)
    prime(api, path)
    exercise(api, path)
    if api == "maxent_save":
        weights, _, labels, _ = load_maxent_params(
            nltk.data.FileSystemPathPointer(str(path))
        )
        assert list(weights) == [1.0] and labels == ["TAG"]


@pytest.mark.parametrize("mode", ("absolute", "traversal", "symlink", "junction"))
@pytest.mark.parametrize("api", APIS)
def test_model_io_rejects_outside_roots(api, mode, roots):
    allowed, outside = roots
    directory = outside_reference(mode, allowed, outside)
    path = target_path(api, directory)
    prime(api, path)
    control = path / "control.txt" if api in ("tagger_save", "maxent_save") else path
    with pytest.raises(PermissionError, match="Security Violation"):
        pathsec.open(str(control), "w")
    before = {
        str(p.relative_to(outside)): p.read_bytes()
        for p in outside.rglob("*")
        if p.is_file()
    }
    with pytest.raises(PermissionError, match="Security Violation"):
        exercise(api, path)
    after = {
        str(p.relative_to(outside)): p.read_bytes()
        for p in outside.rglob("*")
        if p.is_file()
    }
    assert after == before
    assert str(outside) not in nltk.data.path
