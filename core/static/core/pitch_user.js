(function () {
  const chips = Array.from(document.querySelectorAll(".mora-chip"));
  const startInput = document.getElementById("pitch-start");
  const endInput = document.getElementById("pitch-end");
  const resetButton = document.getElementById("reset-pitch");
  const statusText = document.getElementById("pitch-selection-status");

  if (!chips.length || !startInput || !endInput) return;

  let start = null;
  let end = null;

  function setStatus(message) {
    if (statusText) {
      statusText.textContent = message;
    }
  }

  function chipText(index) {
    const chip = chips.find((button) => Number(button.dataset.index) === index);
    return chip ? chip.textContent.trim() : "";
  }

  function clearSelection() {
    start = null;
    end = null;

    startInput.value = "";
    endInput.value = "";

    chips.forEach((chip) => {
      chip.classList.remove("is-selected", "is-start", "is-end");
      chip.setAttribute("aria-pressed", "false");
    });

    setStatus("No pitch selected yet.");
  }

  function updateSelection() {
    chips.forEach((chip) => {
      chip.classList.remove("is-selected", "is-start", "is-end");
      chip.setAttribute("aria-pressed", "false");
    });

    if (start === null) {
      startInput.value = "";
      endInput.value = "";
      setStatus("No pitch selected yet.");
      return;
    }

    if (end === null) {
      startInput.value = start;
      endInput.value = start;

      chips.forEach((chip) => {
        const index = Number(chip.dataset.index);

        if (index === start) {
          chip.classList.add("is-selected", "is-start", "is-end");
          chip.setAttribute("aria-pressed", "true");
        }
      });

      setStatus(`Selected: ${chipText(start)}. Click another mora to extend the pitch.`);
      return;
    }

    const low = Math.min(start, end);
    const high = Math.max(start, end);

    startInput.value = low;
    endInput.value = high;

    chips.forEach((chip) => {
      const index = Number(chip.dataset.index);

      if (index >= low && index <= high) {
        chip.classList.add("is-selected");
        chip.setAttribute("aria-pressed", "true");
      }

      if (index === low) {
        chip.classList.add("is-start");
      }

      if (index === high) {
        chip.classList.add("is-end");
      }
    });

    if (low === high) {
      setStatus(`Selected pitch: ${chipText(low)}`);
    } else {
      setStatus(`Selected pitch: ${chipText(low)} → ${chipText(high)}`);
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