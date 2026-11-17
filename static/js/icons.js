/**
 * Ohmworks Technical Inline SVG Product Art
 * Flat hardware catalogue illustrations in standard palette.
 */

const SVG_ICONS = {
  chip: `<svg viewBox="0 0 64 64" fill="none" stroke="#14151A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="14" y="14" width="36" height="36" rx="2" fill="#FAF8F5" />
    <circle cx="20" cy="20" r="2" fill="#14151A" />
    <!-- pins -->
    <path d="M22 6v8M32 6v8M42 6v8" />
    <path d="M22 50v8M32 50v8M42 50v8" />
    <path d="M6 22h8M6 32h8M6 42h8" />
    <path d="M50 22h8M50 32h8M50 42h8" />
    <rect x="22" y="22" width="20" height="20" stroke-dasharray="2 2" stroke="#575A65" />
  </svg>`,

  board: `<svg viewBox="0 0 64 64" fill="none" stroke="#14151A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="10" y="8" width="44" height="48" rx="3" fill="#FAF8F5" />
    <rect x="24" y="8" width="16" height="8" fill="#EBE7DD" />
    <rect x="18" y="22" width="16" height="16" fill="#14151A" />
    <!-- pin headers -->
    <path d="M14 16v32M50 16v32" stroke="#0E6B6B" stroke-dasharray="1 3" stroke-width="3" />
    <circle cx="42" cy="24" r="2" fill="#FF5A1F" />
  </svg>`,

  sensor: `<svg viewBox="0 0 64 64" fill="none" stroke="#14151A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="12" y="12" width="40" height="40" rx="3" fill="#FAF8F5" />
    <circle cx="32" cy="32" r="12" stroke="#0E6B6B" stroke-width="2" />
    <circle cx="32" cy="32" r="4" fill="#FF5A1F" />
    <path d="M32 14v6M32 44v6M14 32h6M44 32h6" stroke="#575A65" />
  </svg>`,

  capacitor: `<svg viewBox="0 0 64 64" fill="none" stroke="#14151A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M32 6v20M32 38v20" />
    <path d="M14 26h36" stroke-width="3" />
    <path d="M14 38c0 0 10-4 18-4s18 4 18 4" stroke-width="3" stroke="#0E6B6B" />
    <path d="M20 18h6M23 15v6" stroke="#FF5A1F" stroke-width="1.5" />
  </svg>`,

  resistor: `<svg viewBox="0 0 64 64" fill="none" stroke="#14151A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M6 32h14l3-10 6 20 6-20 6 20 6-20 3 10h14" stroke="#14151A" stroke-width="2.5" />
  </svg>`,

  inductor: `<svg viewBox="0 0 64 64" fill="none" stroke="#14151A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M6 36h6c0-10 6-10 6 0c0-10 6-10 6 0c0-10 6-10 6 0c0-10 6-10 6 0h6" stroke="#0E6B6B" stroke-width="2.5" />
  </svg>`,

  transformer: `<svg viewBox="0 0 64 64" fill="none" stroke="#14151A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="12" y="14" width="40" height="36" rx="2" fill="#FAF8F5" />
    <path d="M26 14v36M38 14v36" stroke="#575A65" stroke-dasharray="2 2" />
    <path d="M6 22h6M6 42h6M52 22h6M52 42h6" stroke="#14151A" />
    <circle cx="20" cy="22" r="1.5" fill="#FF5A1F" />
    <circle cx="44" cy="22" r="1.5" fill="#FF5A1F" />
  </svg>`,

  meter: `<svg viewBox="0 0 64 64" fill="none" stroke="#14151A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="14" y="10" width="36" height="44" rx="4" fill="#FAF8F5" />
    <rect x="20" y="16" width="24" height="12" rx="1" fill="#EBE7DD" stroke="#575A65" />
    <circle cx="32" cy="38" r="7" stroke="#14151A" />
    <path d="M32 38l4-4" stroke="#FF5A1F" stroke-width="2" />
    <circle cx="24" cy="48" r="2" fill="#14151A" />
    <circle cx="40" cy="48" r="2" fill="#FF5A1F" />
  </svg>`,

  iron: `<svg viewBox="0 0 64 64" fill="none" stroke="#14151A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 52l18-18" stroke="#575A65" stroke-width="4" />
    <path d="M30 34l12-12" stroke="#14151A" stroke-width="5" />
    <path d="M42 22l14-14-4-2-12 14" fill="#FF5A1F" stroke="#FF5A1F" />
    <circle cx="12" cy="52" r="4" fill="#0E6B6B" />
  </svg>`
};

function getProductSvg(iconKey) {
  return SVG_ICONS[iconKey] || SVG_ICONS['chip'];
}
