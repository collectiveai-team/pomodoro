import localFont from "next/font/local";

export const olivetta = localFont({
  src: [
    {
      path: "./fonts/olivetta/Olivetta-Regular.ttf",
      weight: "400",
      style: "normal",
    },
    {
      path: "./fonts/olivetta/Olivetta-SemiBold.ttf",
      weight: "600",
      style: "normal",
    },
    {
      path: "./fonts/olivetta/Olivetta-Black.ttf",
      weight: "900",
      style: "normal",
    },
  ],
  variable: "--font-olivetta",
  display: "swap",
});

export const leitura = localFont({
  src: [
    {
      path: "./fonts/leitura/Leitura-Italic.otf",
      weight: "400",
      style: "italic",
    },
  ],
  variable: "--font-leitura",
  display: "swap",
});
