(function () {
  const wrap = document.getElementById("mora-wrap");
  const chips = Array.from(document.querySelectorAll(".mora-chip"));
  const startInput = document.getElementById("pitch-start");
  const endInput = document.getElementById("pitch-end");
  const resetButton = document.getElementById("reset-pitch");

  if (!wrap || !chips.length || !startInput || !endInput) return;

  let start = null;
  let end = null;

  function clearSelection() {
    start = null;
    end = null;
    startInput.value = "";
    endInput.value = "";

    chips.forEach((chip) => {
      chip.classList.remove("is-selected", "is-start", "is-end");
    });
  }

  function updateSelection() {
    chips.forEach((chip) => {
      const index = Number(chip.dataset.index);

      chip.classList.remove("is-selected", "is-start", "is-end");

      if (start === null) return;

      if (end === null) {
        if (index === start) {
          chip.classList.add("is-selected", "is-start", "is-end");
        }
        return;
      }

      const low = Math.min(start, end);
      const high = Math.max(start, end);

      if (index >= low && index <= high) {
        chip.classList.add("is-selected");
      }

      if (index === low) {
        chip.classList.add("is-start");
      }

      if (index === high) {
        chip.classList.add("is-end");
      }
    });

    if (start !== null && end === null) {
      startInput.value = start;
      endInput.value = start;
    } else if (start !== null && end !== null) {
      startInput.value = Math.min(start, end);
      endInput.value = Math.max(start, end);
    }
  }

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const index = Number(chip.dataset.index);

      if (start === null) {
        start = index;
        end = null;
      } else if (end === null) {
        end = index;
      } else {
        start = index;
        end = null;
      }

      updateSelection();
    });
  });

  if (resetButton) {
    resetButton.addEventListener("click", clearSelection);
  }

  clearSelection();
})();