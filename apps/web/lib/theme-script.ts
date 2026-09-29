/** Runs before hydration (see layout.tsx) to avoid a flash of the wrong theme. */
export const themeScript = `(function(){try{var p=localStorage.getItem("theme")||"system";var d=p==="dark"||(p==="system"&&window.matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.classList.toggle("dark",d)}catch(e){}})()`;
