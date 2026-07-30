(function () {
  const answerLine = document.getElementById("answer-line");
  const selectedOrderInput = document.getElementById("selected-order");
  const selectedModeInput = document.getElementById("selected-mode");
  const clearButton = document.getElementById("clear-answer");
  const snippetButtons = Array.from(document.querySelectorAll(".snippet-chip"));
  const modeButtons = Array.from(document.querySelectorAll(".mode-button"));

  if (!answerLine || !selectedOrderInput || !selectedModeInput || !clearButton) return;

  let selected = [];
  let mode = "kanji";

  function textFor(buttonOrItem) {
    if (mode === "kana") {
      return buttonOrItem.kana || buttonOrItem.dataset?.kana || buttonOrItem.kanji || buttonOrItem.dataset?.kanji;
    }
    return buttonOrItem.kanji || buttonOrItem.dataset?.kanji;
  }

  function updateHiddenInputs() {
    selectedOrderInput.value = selected.map((item) => item.index).join(",");
    selectedModeInput.value = mode;
  }

  function renderSnippetButtons() {
    snippetButtons.forEach((button) => {
      button.textContent = textFor(button);
    });

    modeButtons.forEach((button) => {
      if (button.dataset.mode === mode) {
        button.classList.add("active");
      } else {
        button.classList.remove("active");
      }
    });
  }

  function renderAnswerLine() {
    answerLine.innerHTML = "";

    selected.forEach((item, position) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "selected-chip";
      chip.textContent = textFor(item);

      chip.addEventListener("click", () => {
        selected.splice(position, 1);

        const originalButton = snippetButtons.find(
          (button) => button.dataset.index === item.index
        );

        if (originalButton) {
          originalButton.disabled = false;
        }

        renderAnswerLine();
        updateHiddenInputs();
      });

      answerLine.appendChild(chip);
    });
  }

  snippetButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const item = {
        index: button.dataset.index,
        kanji: button.dataset.kanji,
        kana: button.dataset.kana,
      };

      selected.push(item);
      button.disabled = true;

      renderAnswerLine();
      updateHiddenInputs();
    });
  });

  modeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      mode = button.dataset.mode;
      renderSnippetButtons();
      renderAnswerLine();
      updateHiddenInputs();
    });
  });

  clearButton.addEventListener("click", () => {
    selected = [];
    snippetButtons.forEach((button) => {
      button.disabled = false;
    });
    renderAnswerLine();
    updateHiddenInputs();
  });

  renderSnippetButtons();
  renderAnswerLine();
  updateHiddenInputs();
})();