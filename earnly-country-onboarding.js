
(() => {
  "use strict";

  const STORAGE_KEY = "earnly_residence_country_v1";
  const WORLDWIDE_KEY = "earnly_include_worldwide_v1";

  const countries = [
    "Canada", "United States", "United Kingdom",
    "Australia", "New Zealand", "India",
    "Philippines", "Nigeria", "South Africa",
    "Ghana", "Kenya", "Pakistan", "Bangladesh",
    "Germany", "France", "Spain", "Italy",
    "Netherlands", "Brazil", "Mexico",
    "Jamaica", "Trinidad and Tobago",
    "United Arab Emirates"
  ];

  const style = document.createElement("style");
  style.textContent = `
    #earnly-country-overlay {
      position: fixed;
      inset: 0;
      z-index: 99999;
      background: rgba(0,0,0,.88);
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 20px;
    }

    #earnly-country-modal {
      background: #141c24;
      color: white;
      width: 100%;
      max-width: 430px;
      padding: 28px;
      border-radius: 20px;
      border: 1px solid #304050;
      font-family: Arial, sans-serif;
    }

    #earnly-country-modal h2 {
      margin-top: 0;
      color: #33e6a1;
    }

    #earnly-country-modal select,
    #earnly-country-modal button {
      width: 100%;
      padding: 14px;
      border-radius: 10px;
      margin-top: 12px;
      font-size: 15px;
      box-sizing: border-box;
    }

    #earnly-country-modal button {
      background: #33e6a1;
      color: #08120e;
      font-weight: bold;
      border: none;
      cursor: pointer;
    }

    #earnly-country-modal select {
      background: #202b36;
      color: white;
      border: 1px solid #465363;
    }

    #earnly-country-modal label {
      display: block;
      margin-top: 15px;
      font-size: 14px;
    }
  `;
  document.head.appendChild(style);

  function getCountry() {
    try {
      return localStorage.getItem(STORAGE_KEY) || "";
    } catch {
      return "";
    }
  }

  function savePreference(country, worldwide) {
    try {
      localStorage.setItem(STORAGE_KEY, country);
      localStorage.setItem(
        WORLDWIDE_KEY,
        String(worldwide)
      );
    } catch {
      console.warn("Country preference could not be saved.");
    }
  }

  function includeWorldwide() {
    try {
      return localStorage.getItem(WORLDWIDE_KEY) !== "false";
    } catch {
      return true;
    }
  }

  function applyCountry() {
    const country = getCountry();
    const selector = document.getElementById("country");

    if (!country || !selector) return;

    const options = Array.from(selector.options);

    const match = options.find(option =>
      option.value.toLowerCase() === country.toLowerCase() ||
      option.textContent.trim().toLowerCase() ===
        country.toLowerCase()
    );

    if (match) {
      selector.value = match.value;
      selector.dispatchEvent(
        new Event("change", { bubbles: true })
      );
    }

    if (typeof window.renderListings === "function") {
      window.renderListings();
    }
  }

  function openCountryModal() {
    if (document.getElementById("earnly-country-overlay")) {
      return;
    }

    const overlay = document.createElement("div");
    overlay.id = "earnly-country-overlay";

    const modal = document.createElement("div");
    modal.id = "earnly-country-modal";

    const title = document.createElement("h2");
    title.textContent = "Welcome to Earnly";

    const description = document.createElement("p");
    description.textContent =
      "Select your country of residence to find earning opportunities available to you.";

    const label = document.createElement("label");
    label.textContent = "Country of residence";

    const select = document.createElement("select");
    select.id = "earnly-residence-select";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select your country";
    select.appendChild(placeholder);

    const available = new Set(countries);

    const existing = document.getElementById("country");
    if (existing) {
      Array.from(existing.options).forEach(option => {
        const name = option.textContent.trim();
        if (
          name &&
          !["all", "worldwide"].includes(
            option.value.toLowerCase()
          )
        ) {
          available.add(name);
        }
      });
    }

    Array.from(available)
      .sort((a, b) => a.localeCompare(b))
      .forEach(country => {
        const option = document.createElement("option");
        option.value = country;
        option.textContent = country;
        select.appendChild(option);
      });

    select.value = getCountry();

    const remoteLabel = document.createElement("label");

    const remoteCheckbox = document.createElement("input");
    remoteCheckbox.type = "checkbox";
    remoteCheckbox.checked = includeWorldwide();
    remoteCheckbox.style.width = "auto";
    remoteCheckbox.style.marginRight = "8px";

    remoteLabel.appendChild(remoteCheckbox);
    remoteLabel.appendChild(
      document.createTextNode(
        "Include worldwide remote opportunities"
      )
    );

    const button = document.createElement("button");
    button.textContent = "Find My Opportunities";

    button.addEventListener("click", () => {
      if (!select.value) {
        alert("Please select your country.");
        return;
      }

      savePreference(
        select.value,
        remoteCheckbox.checked
      );

      overlay.remove();
      applyCountry();

      window.dispatchEvent(
        new CustomEvent("earnly:country-changed", {
          detail: {
            country: select.value,
            includeWorldwide: remoteCheckbox.checked
          }
        })
      );
    });

    modal.append(
      title,
      description,
      label,
      select,
      remoteLabel,
      button
    );

    overlay.appendChild(modal);
    document.body.appendChild(overlay);
  }

  function initialize() {
    if (getCountry()) {
      applyCountry();
    } else {
      openCountryModal();
    }

    const selector = document.getElementById("country");

    if (selector) {
      selector.addEventListener("change", () => {
        const value = selector.value;

        if (
          value &&
          value.toLowerCase() !== "all" &&
          value.toLowerCase() !== "worldwide"
        ) {
          savePreference(value, includeWorldwide());
        }
      });
    }

    const settingsButton = document.createElement("button");
    settingsButton.textContent = "Change Residence Country";
    settingsButton.type = "button";

    settingsButton.style.cssText = `
      position: fixed;
      bottom: 75px;
      right: 12px;
      z-index: 9000;
      background: #20352d;
      color: #33e6a1;
      border: 1px solid #33e6a1;
      border-radius: 10px;
      padding: 9px 12px;
      font-size: 12px;
      cursor: pointer;
    `;

    settingsButton.addEventListener(
      "click",
      openCountryModal
    );

    document.body.appendChild(settingsButton);
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      initialize
    );
  } else {
    initialize();
  }
})();
