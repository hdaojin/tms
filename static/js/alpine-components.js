document.addEventListener("alpine:init", function () {
  window.Alpine.data("tmsShell", function () {
    return {
      commandPaletteOpen: false,
      openCommandPalette() {
        this.commandPaletteOpen = true;
      },
      closeCommandPalette() {
        this.commandPaletteOpen = false;
      },
    };
  });

  window.Alpine.data("feedbackForm", function () {
    return {
      privateTouched: false,
      categoryChanged() {
        if (!this.privateTouched && this.$refs.category.value === "complaint") {
          this.$refs.private.checked = true;
        }
      },
      privateChanged() {
        this.privateTouched = true;
      },
    };
  });

});
