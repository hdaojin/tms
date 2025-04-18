document.addEventListener('DOMContentLoaded', () => {
    const themeController = document.querySelector('.theme-controller');
    const storedTheme = localStorage.getItem('theme');
    if (storedTheme) {
        document.documentElement.setAttribute('data-theme', storedTheme);
        if (themeController) themeController.checked = storedTheme === 'dark';
    }
    if (themeController) {
        themeController.addEventListener('change', (e) => {
            const theme = e.target.checked ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('theme', theme);
        });
    }
});