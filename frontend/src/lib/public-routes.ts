export const PUBLIC_ROUTES: string[] = [
  "/",
  "/privacy",
  "/terms",
  "/how-it-works",
  "/api",
];

export function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(route + "/"),
  );
}
