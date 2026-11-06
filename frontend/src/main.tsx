import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth";
import { Home, Login, Register } from "./pages/auth/AuthPages";
import AppLayout from "./pages/app/AppLayout";
import Apartments from "./pages/app/Apartments";
import Bookings from "./pages/app/Bookings";
import Calendar from "./pages/app/Calendar";
import { Analytics, Expenses } from "./pages/app/Finance";
import { Guests, Reviews } from "./pages/app/GuestsReviews";
import Settings from "./pages/app/Settings";
import ApartmentPage from "./pages/guest/ApartmentPage";
import BookingPage from "./pages/guest/BookingPage";
import Storefront from "./pages/guest/Storefront";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<Calendar />} />
            <Route path="bookings" element={<Bookings />} />
            <Route path="guests" element={<Guests />} />
            <Route path="reviews" element={<Reviews />} />
            <Route path="apartments" element={<Apartments />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="expenses" element={<Expenses />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="/b/:token" element={<BookingPage />} />
          <Route path="/:slug" element={<Storefront />} />
          <Route path="/:slug/:apt" element={<ApartmentPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>,
);
