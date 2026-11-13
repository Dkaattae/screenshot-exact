"""Unit tests for the outfit rules. These match frontend/src/test/try-on-rules.test.ts."""

import copy

import pytest

from app.rules import edit_state, outfit_item_ids, reused_layers

STATE = {
    "body": {"kind": "default", "id": "body"},
    "background_id": "bg",
    "base": {"mode": "top_bottom", "top_id": "top", "bottom_id": "jeans", "tucked": False},
    "outer": {"item_id": "jacket", "open": False},
    "accessory": {"item_id": "bag"},
    "style_notes": {},
}


def with_changes(**changes):
    state = copy.deepcopy(STATE)
    state.update(changes)
    return state


def reused(previous, current):
    return [layer["reused"] for layer in reused_layers(previous, current)]


class TestOutfitItemIds:
    def test_top_mode_lists_every_piece_base_first(self):
        assert outfit_item_ids(STATE) == ["top", "jeans", "jacket", "bag"]

    def test_one_piece_mode_lists_only_the_one_piece_as_base(self):
        state = with_changes(base={"mode": "one_piece", "one_piece_id": "dress"}, accessory=None)
        assert outfit_item_ids(state) == ["dress", "jacket"]

    def test_skips_a_bottom_not_chosen_yet(self):
        base = {"mode": "top_bottom", "top_id": "top", "bottom_id": None, "tucked": False}
        assert outfit_item_ids(with_changes(base=base, outer=None, accessory=None)) == ["top"]


class TestEditState:
    @pytest.mark.parametrize(
        ("message", "tucked", "summary"),
        [
            ("tuck in the shirt", True, "Shirt tucked in."),
            ("Please TUCK it", True, "Shirt tucked in."),
            ("untuck the shirt", False, "Shirt untucked."),
        ],
    )
    def test_tuck_and_untuck(self, message, tucked, summary):
        state, change_summary = edit_state(STATE, message)
        assert state["base"]["tucked"] is tucked
        assert change_summary == summary

    @pytest.mark.parametrize(
        ("message", "is_open", "summary"),
        [
            ("open the jacket", True, "Outer layer opened."),
            ("close the jacket", False, "Outer layer closed."),
            ("closed please", False, "Outer layer closed."),
        ],
    )
    def test_open_and_close_outer(self, message, is_open, summary):
        state, change_summary = edit_state(STATE, message)
        assert state["outer"]["open"] is is_open
        assert change_summary == summary

    def test_tuck_is_ignored_in_one_piece_mode(self):
        state = with_changes(base={"mode": "one_piece", "one_piece_id": "dress"}, outer=None)
        result, summary = edit_state(state, "tuck it in")
        assert result == state
        assert "wasn't understood" in summary

    def test_open_without_an_outer_changes_nothing(self):
        state = with_changes(outer=None)
        result, summary = edit_state(state, "open the jacket")
        assert result["outer"] is None
        assert "wasn't understood" in summary

    def test_unknown_request_changes_nothing(self):
        result, summary = edit_state(STATE, "make it purple")
        assert result == STATE
        assert "wasn't understood" in summary

    def test_does_not_modify_its_input(self):
        original = copy.deepcopy(STATE)
        edit_state(STATE, "tuck in and open")
        assert original == STATE


class TestReusedLayers:
    def test_nothing_is_reused_without_a_previous_job(self):
        assert reused(None, STATE) == [False, False, False]

    def test_everything_is_reused_when_nothing_changed(self):
        assert reused(STATE, copy.deepcopy(STATE)) == [True, True, True]

    def test_only_accessory_changed(self):
        assert reused(STATE, with_changes(accessory={"item_id": "hat"})) == [True, True, False]

    def test_only_outer_changed(self):
        outer = {"item_id": "jacket", "open": True}
        assert reused(STATE, with_changes(outer=outer)) == [True, False, False]

    @pytest.mark.parametrize(
        "changes",
        [
            {"base": {**STATE["base"], "tucked": True}},
            {"body": {"kind": "default", "id": "other"}},
            {"background_id": "beach"},
            {"style_notes": {"top": "sleeves rolled up"}},
        ],
    )
    def test_base_changes_invalidate_every_layer(self, changes):
        assert reused(STATE, with_changes(**changes)) == [False, False, False]
