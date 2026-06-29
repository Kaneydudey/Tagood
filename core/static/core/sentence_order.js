(function () {
  const answerLine = document.getElementById("answer-line");
  const selectedOrderInput = document.getElementById("selected-order");
  const clearButton = document.getElementById("clear-answer");
  const snippetButtons = Array.from(document.querySelectorAll(".snippet-chip"));

  if (!answerLine || !selectedOrderInput || !clearButton) return;

  let selected = [];

  function updateHiddenInput() {
    selectedOrderInput.value = selected.map((item) => item.index).join(",");
  }

  function renderAnswerLine() {
    answerLine.innerHTML = "";

    selected.forEach((item, position) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "selected-chip";
      chip.textContent = item.text;

      chip.addEventListener("click", () => {
        selected.splice(position, 1);

        const originalButton = snippetButtons.find(
          (button) => button.dataset.index === item.index
        );

        if (originalButton) {
          originalButton.disabled = false;
        }

        renderAnswerLine();
        updateHiddenInput();
      });

      answerLine.appendChild(chip);
    });
  }

  snippetButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const item = {
        index: button.dataset.index,
        text: button.dataset.text,
      };

      selected.push(item);
      button.disabled = true;

      renderAnswerLine();
      updateHiddenInput();
    });
  });

  clearButton.addEventListener("click", () => {
    selected = [];
    snippetButtons.forEach((button) => {
      button.disabled = false;
    });
    renderAnswerLine();
    updateHiddenInput();
  });
})();