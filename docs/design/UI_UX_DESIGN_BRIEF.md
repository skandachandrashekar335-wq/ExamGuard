# ExamGuard UI/UX Design Brief

## Approved Visual Direction

### Editorial does not mean document-like.

The interface should remain visually composed, interactive, and product-like. Key principles:

- **Sophisticated typography-first design**: Type is the primary visual vehicle; hierarchy, scale, and contrast drive attention
- **Geometric/editorial/luxury-brutalist influence**: Clean lines, structured layouts, intentional whitespace; reference luxury editorial design without falling into document-like formatting
- **Monochrome high-contrast palette**: 
  - Light editorial base: `#F2F2F2`
  - Primary: `#111111`
  - Gray depth layers: `#888888`, `#F7F7F7`, `#F0F0F0`, `#D9D9D9`, `#B6B5B5`, `#AEAEAE`
  - Borders: `rgba(17, 17, 17, 0.1)`, `rgba(17, 17, 17, 0.2)`
  - Surface: `var(--bg-subtle)` = `#F7F7F7`, `var(--bg-raised)` = `var(--gray-20)` = `#D9D9D9`
- **Light editorial base**: `#F2F2F2` background throughout; dark-on-light reading pattern
- **Typographic hierarchy**: 
  - Display: Playfair Display or similar serif, large scale, high contrast
  - Body: Source Serif 4 or similar serid for readability
  - Mono: JetBrains Mono or similar for code/UI labels, status, signals
  - Text weight contrast: bold for headlines, regular for body, medium for captions
- **12-column layout** with appropriate gutters; responsive behavior at sm/md/lg breakpoints
- **Spacing/system**: Consistent vertical and horizontal spacing; scale-based spacing (not arbitrary)

### Navigation

- **Top sticky header**: Brand + navigation links + user info (name/email/role) + LOG OUT
- **Brand**: "EXAMGUARD" in mono display type; consistent across all pages
- **Navigation links**: PRODUCT, VERIFICATION, SECURITY, ANALYTICS, AUDIT (role-dependent)
- **Secondary CTA**: "ACCESS SYSTEM" button (primary call-to-action on landing)
- **Responsive**: Collapses to hamburger/menu on mobile; full horizontal bar on desktop
- **Hover states**: Color transition (from gray to primary black); underline or background change
- **Active state**: Indicates current page; subtle background or border indicator

### Cards and Components

- **Card style**: `bg-[var(--bg-raised)]` = `#D9D9D9` with `border border-[var(--border)]` = `rgba(17, 17, 17, 0.1)`
- **Border-strong**: `rgba(17, 17, 17, 0.2)` for primary calls or selected items
- **Rounding**: **Zero border-radius** — no rounded corners; all edges straight; consistent with "no neon sci-fi", "no terminal aesthetic" directives
- **Hover states**: Background or border color shift (not random); consistent across all interactive components
- **Focus states**: Visible focus indicator (contrast against monochrome); accessible but subtle

### Camera/Verification Visual Language

- **Camera component**: `FaceGeometry` component; visual indication of camera state (idle/scan/frame)
- **Pipeline visualization**: CAMERA → IDENTITY → LIVENESS → HALL TICKET → SEAT → EVIDENCE → DECISION
- **Signal display**: Labels with `eg-mono` typography; percentage bars for numeric scores; provider info
- **Decision display**: Exact domain vocabulary: MATCH, NO_MATCH, INCONCLUSIVE, PENDING; no frontend-computed confidence scores
- **Evidence display**: Signal types with labels: `similarity_score`, `liveness_score`, `liveness_signal`, `image_quality`; percentage bars for numeric scores; provider info and confidence values; details text when available
- **No fake dashboard numbers**: All data from backend API; no fabricated metrics or stats
- **No red/amber alarm styling** unless explicitly required by the product state (security language is monochrome, not colored alarm styling)
- **No huge empty spaces**: Layout density appropriate; no gratuitous whitespace; 12-column system with gutters

### Color Usage

- **Monochrome palette only**: No neon blue, green, purple, or other accent colors
- **No gradient backgrounds** (unless specifically part of the editorial design system)
- **No branded colors** beyond the established "EXAMGUARD" identity
- **Text colors**: `var(--black)` = `#111111` for primary; `var(--gray-55)` = `#888888` for secondary; `var(--gray-40)` for tertiary; `var(--gray-20)` for subtle backgrounds
- **Link/hover states**: Transition from secondary gray to primary black; no underlines unless part of the design system; color change only
- **Border colors**: `rgba(17, 17, 17, 0.1)` for subtle borders; `rgba(17, 17, 17, 0.2)` for strong borders (primary actions, selected items)

### Typography

- **Headings**: Display scale; Playfair Display / Source Serif 4 / JetBrains Mono; decreasing sizes (lg → xl → 2xl → 3xl → 4xl); letter-spacing tight; line-height scale; all-caps or capitalize usage semantic and intentional
- **Body text**: Source Serif 4 or similar serif; line-height scale; comfortable line length; 60-80 characters per line optimal
- **Mono/Label text**: JetBrains Mono / similar; used for status, signals, timestamps, counts; monospace for code-like display; consistent vertical alignment
- **Contrast ratios**: Accessible minimums met; `text-[var(--black)]` on `bg-[var(--bg-light)]` = `#F2F2F2`; sufficient contrast for all text including captions and metadata
- **No underline** unless specifically part of the design system (links may use color change only)

### Component Consistency

- **Button styles**: Primary (uppercase, tracking-wider, padded, bordered-primary); Secondary (text or outlined); Disabled (opacity, cursor not-allowed)
- **Input fields**: Border `var(--border)` = `rgba(17, 17, 17, 0.1)`; focus state: `var(--border-strong)` = `rgba(17, 17, 17, 0.2)`; no glowing or animated borders; consistent padding and spacing
- **Select/dropdown**: Arrow indicator; option hover state; disabled option styling; searchable if needed
- **Badge/Status display**: Monochrome only; text label only; no colored circles or dots; `var(--gray-55)` for secondary status; `var(--black)` for primary status
- **Table styling**: Monochrome; zebra striping optional but in monochrome grays only; borderless or `var(--border)`; hover state in subtle gray; no colored row highlights

### Reduced Motion

- **No automatic animations** that cannot be disabled
- **Respect prefers-reduced-motion**: If user enables reduced motion, all non-essential animations/slide transitions are disabled
- **Transitions**: Only essential status changes; no automatic carousel/slider; hover transitions limited to 150ms or less

### Performance Requirements

- **Page load**: < 2 seconds on typical connection; code-splitting where appropriate; static assets cached
- **Image optimization**: No large uncompressed images; if images used (hall tickets, reference photos), optimized and compressed
- **Font loading**: `font-display: swap` or equivalent; no FOUC (Flash of Unstyled Text); system fallback available
- **Bundle size**: Reasonable; no unnecessary dependencies; tree-shakeable imports

### Accessibility (a11y)

- **Color contrast**: Accessible minimums; `var(--black)` on `var(--bg-light)` = `#F2F2F2`; all text including captions and metadata
- **Focus visible**: Clear focus indicator; not removed via `outline: none` without replacement; consistent styling across all focusable elements
- **Keyboard navigation**: Tab order logical; Escape closes modals/dropdowns; Arrow keys navigate within components
- **Screen reader**: Semantic HTML; aria-labels where meaningful; no content conveyed only through color; meaningful alt text for informative images (decorative images have empty alt)
- **Form labels**: Associated with inputs via `htmlFor`/`id` pairing; placeholder text not substitute for label

### Image/Object/Text Composition

- **Camera/face graphics**: `FaceGeometry` component; stylized representation; no realistic camera images; abstract visual language; opacity/animation for state indication
- **No human images** in dashboard/header unless specifically required; placeholder initials avatar if used
- **Iconography**: Line-icon style; monochrome; consistent stroke weight; `eg-mono` typography for labels alongside
- **Text composition**: Ragged right acceptable; hyphenation optional; no widows/orphans at extreme margins; consistent vertical rhythm
- **Data visualization**: If charts/graphs used: monochrome color palette; accessible via text labels; keyboard-navigable; screen-reader friendly descriptions

### Motion Principles

- **Purposeful motion**: Every animation has a reason (state change, navigation transition, feedback); no decorative motion
- **Easing**: ease-out or ease-in-out for natural feel; duration: 150-300ms; no sudden/jarring motions
- **Sequential reveals**: Page elements appear in logical order; not all at once; staggered entrance if used (respects reduced motion)
- **Hover interactions**: Scale or color change on interactive elements; no click-press ripple effects; no marquee or scrolling text

### Responsive Behavior

- **Mobile-first** approach: mobile layout first, then expand to tablet/desktop
- **12-column grid**: Consistent across all breakpoints; gutters consistent; content reflows gracefully
- **Navigation**: Collapsible hamburger on mobile; full bar on desktop; drawer or top bar alternatives
- **Typography**: Scclable fluid typography; `clamp()` or similar for viewport-relative sizing; headings scale down on mobile
- **Grid items**: Wrap gracefully; no overflow; `overflow-hidden` on container if needed

### Alignment Rules

- **Vertical center**: Flexbox `items-center`; or grid `align-items-center`; or block with known height and `margin-top: calc(50% - ...)`
- **Horizontal center**: Flexbox `justify-center`; or grid `justify-center`; text-center utility; or block with auto margins
- **Page layout**: Max-width container (e.g., `max-w-7xl mx-auto px-6 sm:px-10`); consistent margins; no edge-to-edge content except hero/base backgrounds
- **Component alignment**: Consistent within groups; mix of aligned and justified elements; no misaligned children within same parent

### Image/Object/Text Composition

- **Camera/face graphics**: `FaceGeometry` component; abstract visual; state-indicating opacity/animation; no realistic camera photos
- **No human images** in dashboard/header unless specifically required; placeholder initials avatar if used
- **Iconography**: Line-icon style; monochrome; consistent stroke weight; used alongside `eg-mono` typography for labels
- **Text composition**: Ragged right acceptable; hyphenation optional; no widows/orphans at extreme margins; consistent vertical rhythm; 60-80 chars per line optimal for body
- **Data visualization**: If charts/graphs used: monochrome palette; accessible via text labels; keyboard-navigable; screen-reader friendly descriptions

## Design System Tokens (CSS Custom Properties)

```css
:root {
  --white: #FFFFFF;
  --bg-light: #F2F2F2;
  --bg-subtle: #F7F7F7;
  --bg-muted: #F0F0F0;
  --black: #111111;
  --gray-55: #888888;
  --gray-20: #D9D9D9;
  --gray-40: #B6B5B5;
  --gray-30: #AEAEAE;
  --dark-section: #1E1E1E;
  --bg-base: var(--white);
  --bg-surface: var(--bg-subtle);
  --bg-raised: var(--gray-20);
  --border: rgba(17, 17, 17, 0.1);
  --border-strong: rgba(17, 17, 17, 0.2);
  --text-primary: var(--black);
  --text-secondary: var(--gray-40);
  --text-tertiary: var(--gray-55);
}
```

## Prohibited Elements

- **Neon sci-fi styling**: No glowing, neon colors, or cyberpunk aesthetics
- **Terminal aesthetic**: No terminal/console-like appearance; this is a product, not a dev terminal
- **Random absolute positioning**: Layout must use consistent positioning system (flex/grid)
- **Huge empty spaces**: No gratuitous whitespace; layout should be dense and purposeful
- **Fake dashboard numbers**: All data must come from backend API; no fabricated metrics or stats
- **Red/amber alarm styling** unless explicitly required by the product state (security language is monochrome, not colored alarm styling)
- **Fake dashboard numbers**: No invented metrics, stats, or performance numbers
- **Monochrome security language**: All security/status terminology in grayscale; no color-coded alarm bars unless explicitly part of the design system

## Component Reference

### Button Styles

- **Primary**: Uppercase, tracking-wider, padded, bordered-primary (`border border-[var(--border)] hover border-[var(--white)]`); secondary: text or outlined; disabled: opacity, cursor not-allowed
- **States**: Hover (color transition from secondary gray to primary black); active; disabled (opacity, cursor not-allowed)

### Input Styles

- **Border**: `var(--border)` = `rgba(17, 17, 17, 0.1)`; focus state: `var(--border-strong)` = `rgba(17, 17, 17, 0.2)`; no glowing or animated borders; consistent padding (e.g., `px-4 py-2` or appropriate for component)
- **Invalid state**: subtle error state; no red coloring (monochrome only); border may shift to stronger gray

### Typography Scale

- **Display**: `text-[clamp(72px,10vw,180px)]` or similar; headline sizes; Playfair Display / Source Serif 4
- **Body**: `text-base` or `text-sm`; Source Serif 4 or similar; line-height scale
- **Mono/Label**: `text-[var(--gray-55)] text-xs uppercase tracking-wider`; JetBrains Mono or similar; status, signals, timestamps
- **Captions/small**: `text-[var(--gray-55)] text-xs`; meta information, timestamps, provider info

### Color Palette

- `--white`: `#FFFFFF`
- `--bg-light`: `#F2F2F2` (base background)
- `--gray-55`: `#888888` (secondary text)
- `--gray-40`: `#B6B5B5` (muted/secondary)
- `--gray-20`: `#D9D9D9` (card/raised surface)
- `--black`: `#111111` (primary text)
- `--border`: `rgba(17, 17, 17, 0.1)` (subtle borders)
- `--border-strong`: `rgba(17, 17, 17, 0.2)` (strong borders, primary actions)

### Layout Spacing

- **Container**: `max-w-7xl mx-auto px-6 sm:px-10`; `max-w-5xl mx-auto px-6 sm:px-10` for narrower pages
- **Section padding**: `py-12 sm:py-16`; `py-8 sm:py-12` for subsections; `py-4 sm:py-6` for compact sections
- **Gap**: `grid gap-4`; `grid gap-6`; `gap-4`; `gap-6`; consistent across grid and flex layouts
- **Margin**: `my-8 sm:my-12`; `mx-6 sm:mx-10`; consistent vertical/horizontal spacing

## Visual Do's and Don'ts

### Do's

- Use the monochrome palette consistently throughout
- Maintain typographic hierarchy and scale
- Keep layouts dense and purposeful; no gratuitous whitespace
- Use flexbox/grid for all layout; no random absolute positioning
- respect prefers-reduced-motion; all non-essential animations disabled
- Ensure accessible color contrast throughout
- Use meaningful, semantic HTML; aria-labels where appropriate
- Keep component consistency across all pages

### Don'ts

- Use neon sci-fi styling or terminal aesthetic
- Use random absolute positioning for layout elements
- Include huge empty spaces without purpose
- Include fake dashboard numbers or fabricated metrics
- Use red/amber alarm styling unless explicitly required (security is monochrome)
- Introduce paid APIs, cloud AI, or biometric APIs beyond what's implemented
- Disable accessibility features or contrast requirements
- Use color as the only means of conveying information

## Development Workflow

- **Design comps**: Reference the approved visual direction; no new redesigns during this task
- **Component library**: Existing components (Button, Input, Card, etc.) should follow this brief; no new component styles unless required
- **Typography**: Use the type scale and fonts specified; no custom font additions without approval
- **Color**: Strict monochrome palette; no accent colors unless specifically approved
- **Spacing**: Use the specified spacing scale; no arbitrary margins/paddings
- **Responsive**: Test at mobile (375px), tablet (768px), desktop (1440px); ensure graceful reflow
- **Accessibility**: Test color contrast; test keyboard navigation; test screen reader flow
- **Performance**: Profile page load; optimize images; ensure reasonable bundle size

## Final Check Before Implementation

- Does the visual design match the approved editorial/monochrome direction?
- Are all prohibited elements absent?
- Is the typography hierarchy correct and consistent?
- Is the color palette monochrome throughout?
- Is the layout dense and purposeful with no gratuitous whitespace?
- Does it respect reduced motion preferences?
- Is the navigation consistent and role-appropriate?
- Are all components consistent with the design system tokens?
- Is the build successful (TypeScript, lint, production build)?