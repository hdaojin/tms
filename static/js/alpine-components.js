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

  window.Alpine.data("feedbackAttachmentPicker", function () {
    let pasteTarget = null;
    let pasteHandler = null;

    return {
      files: [],
      previewUrls: [],
      error: "",
      dragging: false,
      maxCount: 10,
      maxTotalBytes: 50 * 1024 * 1024,

      init() {
        this.maxCount = Number(this.$el.dataset.maxCount || 10);
        this.maxTotalBytes = Number(this.$el.dataset.maxTotalBytes || 52428800);
        pasteTarget = document;
        if (pasteTarget) {
          pasteHandler = (event) => this.handlePaste(event);
          pasteTarget.addEventListener("paste", pasteHandler);
        }
      },

      isImage(file) {
        if (file.type && file.type.startsWith("image/")) {
          return /\.(jpe?g|png|webp)$/i.test(file.name || "") || ["image/jpeg", "image/png", "image/webp"].includes(file.type);
        }
        return /\.(jpe?g|png|webp)$/i.test(file.name || "");
      },

      fileKey(file, index) {
        return `${file.name}-${file.size}-${file.lastModified}-${index}`;
      },

      formatSize(size) {
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
        return `${(size / 1024 / 1024).toFixed(2)} MB`;
      },

      validateFiles(files) {
        if (files.length > this.maxCount) return `每次最多选择 ${this.maxCount} 个附件。`;
        const totalSize = files.reduce((total, file) => total + (file.size || 0), 0);
        if (totalSize > this.maxTotalBytes) return "本次附件总大小不能超过 50MB。";
        if (files.some((file) => file.size > 20 * 1024 * 1024)) return "单个附件不能超过 20MB。";
        return "";
      },

      setFiles(files) {
        const nextFiles = Array.from(files || []);
        const validationError = this.validateFiles(nextFiles);
        if (validationError) {
          this.error = validationError;
          return;
        }
        this.error = "";
        this.files = nextFiles;
        this.syncInput();
        this.refreshPreviews();
      },

      addFiles(files) {
        this.setFiles([...this.files, ...Array.from(files || [])]);
      },

      handleChange() {
        this.setFiles(this.$refs.input.files);
      },

      handleDragOver(event) {
        event.preventDefault();
        this.dragging = true;
      },

      handleDragLeave(event) {
        event.preventDefault();
        this.dragging = false;
      },

      handleDrop(event) {
        event.preventDefault();
        this.dragging = false;
        this.addFiles(event.dataTransfer.files);
      },

      handlePaste(event) {
        const items = Array.from((event.clipboardData && event.clipboardData.items) || []);
        const pastedImages = items
          .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
          .map((item) => item.getAsFile())
          .filter(Boolean)
          .map((file) => {
            if (file.name) return file;
            const now = new Date();
            const stamp = [now.getFullYear(), now.getMonth() + 1, now.getDate(), now.getHours(), now.getMinutes(), now.getSeconds()]
              .map((value) => String(value).padStart(2, "0"))
              .join("");
            return new File([file], `screenshot-${stamp}.png`, { type: file.type || "image/png" });
          });
        if (pastedImages.length) {
          event.preventDefault();
          this.addFiles(pastedImages);
        }
      },

      removeFile(index) {
        this.files.splice(index, 1);
        this.error = "";
        this.syncInput();
        this.refreshPreviews();
      },

      syncInput() {
        if (typeof DataTransfer === "undefined") return;
        const transfer = new DataTransfer();
        this.files.forEach((file) => transfer.items.add(file));
        this.$refs.input.files = transfer.files;
      },

      refreshPreviews() {
        this.previewUrls.forEach((url) => {
          if (url) URL.revokeObjectURL(url);
        });
        this.previewUrls = this.files.map((file) => (this.isImage(file) ? URL.createObjectURL(file) : ""));
      },

      destroy() {
        if (pasteTarget && pasteHandler) {
          pasteTarget.removeEventListener("paste", pasteHandler);
        }
        this.previewUrls.forEach((url) => {
          if (url) URL.revokeObjectURL(url);
        });
      },
    };
  });
});
