from __future__ import annotations

from typing import Callable

from textual.widgets import SelectionList


class VirtualChapterList(SelectionList[int]):
    """Большой список глав с чекбоксами через SelectionList.

    Совместимый API:
    - update_data
    - select_all
    - deselect_all
    - get_selected_indices
    - set_range
    - scroll_to_top
    - scroll_to_bottom
    """

    CSS_PATH = "../styles/virtual_chapter_list.tcss"

    def __init__(
        self,
        chapters_data: list[dict] | None = None,
        on_selection_changed: Callable[[], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._chapters_data: list[dict] = chapters_data or []
        self._on_selection_changed = on_selection_changed
        self._suppress_callback = False
        self._ready_for_callbacks = False

    def on_mount(self) -> None:
        # На старте не дергаем callback, чтобы экран успел инициализировать ссылки.
        self.update_data(self._chapters_data, emit=False)
        self._ready_for_callbacks = True

    def _notify_changed(self) -> None:
        if self._ready_for_callbacks and self._on_selection_changed:
            self._on_selection_changed()

    def _make_options(
        self,
        chapters: list[dict],
        selected_indices: set[int],
    ) -> list[tuple[str, int, bool]]:
        options: list[tuple[str, int, bool]] = []
        for idx, chapter in enumerate(chapters):
            title = str(chapter.get("title", "")).strip()
            prompt = f"{idx + 1}. {title}" if title else f"{idx + 1}."
            options.append((prompt, idx, idx in selected_indices))
        return options

    def update_data(self, new_chapters_data: list[dict] | None, emit: bool = True) -> None:
        """Обновить список глав и сохранить выбор по совпадающим индексам."""
        new_chapters_data = new_chapters_data or []
        old_selected = set(self.selected)

        self._chapters_data = new_chapters_data
        self._suppress_callback = True
        try:
            self.clear_options()
            if self._chapters_data:
                self.add_options(self._make_options(self._chapters_data, old_selected))
        finally:
            self._suppress_callback = False

        self.refresh(layout=True)
        self.scroll_home(animate=False, immediate=True)

        if emit:
            self._notify_changed()

    def on_selection_list_selected_changed(
        self,
        event: SelectionList.SelectedChanged[int],
    ) -> None:
        """Срабатывает на клик и на программные изменения."""
        if self._suppress_callback:
            return
        self._notify_changed()

    def select_all(self) -> None:
        self._suppress_callback = True
        try:
            super().select_all()
        finally:
            self._suppress_callback = False
        self._notify_changed()

    def deselect_all(self) -> None:
        self._suppress_callback = True
        try:
            super().deselect_all()
        finally:
            self._suppress_callback = False
        self._notify_changed()

    def get_selected_indices(self) -> list[int]:
        """Возвращает 1-based индексы выбранных глав."""
        return [value + 1 for value in sorted(self.selected)]

    def set_range(self, from_idx: int, to_idx: int) -> None:
        """Выбрать диапазон глав по 1-based индексам, включая обе границы."""
        if not self._chapters_data:
            return

        start = max(1, min(from_idx, to_idx))
        end = min(len(self._chapters_data), max(from_idx, to_idx))

        self._suppress_callback = True
        try:
            for chapter_idx in range(start - 1, end):
                self.select(chapter_idx)
        finally:
            self._suppress_callback = False

        self._notify_changed()

    def scroll_to_top(self) -> None:
        self.scroll_home(animate=False, immediate=True)

    def scroll_to_bottom(self) -> None:
        self.scroll_end(animate=False, immediate=True)
