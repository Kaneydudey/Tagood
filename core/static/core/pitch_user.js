(function () {
  const wrap = document.getElementById("mora-wrap");
  if (!wrap) return;

  const chips = Array.from(wrap.querySelectorAll(".mora-chip"));
  const startInput = document.getElementById("pitch-start");
  const endInput = document.getElementById("pitch-end");
  const resetBtn = document.getElementById("pitch-reset");

  let start = null;
  let end = null;

  function render() {
    chips.forEach((chip) => {
      const i = parseInt(chip.dataset.index, 10);
      chip.classList.remove("selected");

      if (start !== null && end !== null) {
        const lo = Math.min(start, end);
        const hi = Math.max(start, end);
        if (i >= lo && i <= hi) chip.classList.add("selected");
      }
    });

    startInput.value = start === null ? "" : String(Math.min(start, end ?? start));
    endInput.value = end === null ? "" : String(Math.max(start ?? end, end));
  }

  function clear() {
    start = null;
    end = null;
    render();
  }

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const i = parseInt(chip.dataset.index, 10);

      if (start === null) {
        start = i;
        end = null;
        render();
        return;
      }

      if (end === null) {
        end = i; // can be same mora as start
        render();
        return;
      }

      // third click resets
      clear();
    });
  });

  resetBtn.addEventListener("click", clear);

  render();
})();