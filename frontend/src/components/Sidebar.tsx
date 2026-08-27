import { NavLink } from "react-router-dom";
import type { ReactElement } from "react";

interface Destination {
  readonly to: string;
  readonly label: string;
  readonly hebrew: string;
}

const DESTINATIONS: readonly Destination[] = [
  { to: "/", label: "Today", hebrew: "היום" },
  { to: "/roadmap", label: "Roadmap", hebrew: "מפת דרכים" },
  { to: "/pace", label: "Pace", hebrew: "קצב" },
  { to: "/stats", label: "Stats", hebrew: "מאזן" },
  { to: "/chavrusas", label: "Chavrusas", hebrew: "חברותות" },
  { to: "/alignment", label: "Alignment", hebrew: "עין משפט" },
  { to: "/sequence", label: "Sequence", hebrew: "סדר הלימוד" },
  { to: "/tags", label: "Tags", hebrew: "תוויות" },
  { to: "/maintenance", label: "Maintenance", hebrew: "תחזוקה" },
];

export function Sidebar(): ReactElement {
  return (
    <nav className="sidebar" aria-label="Sections">
      <p className="sidebar__brand he" dir="rtl" lang="he">
        סדרה
      </p>
      <ul className="sidebar__list">
        {DESTINATIONS.map((destination) => (
          <li key={destination.to}>
            <NavLink className="sidebar__link" to={destination.to} end={destination.to === "/"}>
              <span className="he sidebar__he" dir="rtl" lang="he">
                {destination.hebrew}
              </span>
              <span className="sidebar__en">{destination.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
