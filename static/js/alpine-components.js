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
      init() {
        this.applyCategoryDefault();
      },
      categoryChanged() {
        this.applyCategoryDefault();
      },
      applyCategoryDefault() {
        if (this.privateTouched) return;
        const defaultPrivateValues = JSON.parse(
          this.$refs.category.dataset.defaultPrivateValues || "[]",
        );
        this.$refs.private.checked = defaultPrivateValues.includes(this.$refs.category.value);
      },
      privateChanged() {
        this.privateTouched = true;
      },
    };
  });

});
