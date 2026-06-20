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
});
