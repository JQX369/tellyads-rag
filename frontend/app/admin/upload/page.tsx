"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { Button, Badge } from "@/components/ui";

interface UploadFormData {
  brand_name: string;
  product_name: string;
  year: string;
  product_category: string;
  country: string;
  description: string;
}

const categories = [
  { id: "automotive", name: "Automotive" },
  { id: "fmcg", name: "FMCG" },
  { id: "finance", name: "Finance" },
  { id: "tech", name: "Technology" },
  { id: "retail", name: "Retail" },
  { id: "entertainment", name: "Entertainment" },
  { id: "telecom", name: "Telecom" },
  { id: "travel", name: "Travel" },
  { id: "pharma", name: "Pharma" },
  { id: "alcohol", name: "Alcohol" },
  { id: "charity", name: "Charity" },
  { id: "government", name: "Government" },
  { id: "b2b", name: "B2B" },
  { id: "other", name: "Other" },
];

export default function UploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const [formData, setFormData] = useState<UploadFormData>({
    brand_name: "",
    product_name: "",
    year: new Date().getFullYear().toString(),
    product_category: "",
    country: "GB",
    description: "",
  });

  // Check auth
  useEffect(() => {
    const authToken = sessionStorage.getItem("admin_auth");
    if (authToken !== "authenticated") {
      router.push("/admin");
    } else {
      setIsAuthenticated(true);
    }
  }, [router]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file type
      if (!file.type.startsWith("video/")) {
        setError("Please select a video file");
        return;
      }
      // Validate file size (max 500MB)
      if (file.size > 500 * 1024 * 1024) {
        setError("File size must be less than 500MB");
        return;
      }
      setSelectedFile(file);
      setError("");
    }
  };

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!selectedFile) {
      setError("Please select a video file");
      return;
    }

    if (!formData.brand_name.trim()) {
      setError("Brand name is required");
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    try {
      // Create FormData for upload
      const uploadData = new FormData();
      uploadData.append("video", selectedFile);
      uploadData.append("brand_name", formData.brand_name);
      uploadData.append("product_name", formData.product_name);
      uploadData.append("year", formData.year);
      uploadData.append("product_category", formData.product_category);
      uploadData.append("country", formData.country);
      uploadData.append("description", formData.description);

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

      // Simulate upload progress (in production, use XMLHttpRequest for real progress)
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => Math.min(prev + 10, 90));
      }, 500);

      const response = await fetch(`${apiUrl}/api/admin/upload`, {
        method: "POST",
        body: uploadData,
      });

      clearInterval(progressInterval);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Upload failed");
      }

      setUploadProgress(100);
      setSuccess(true);

      // Reset form after success
      setTimeout(() => {
        setSelectedFile(null);
        setFormData({
          brand_name: "",
          product_name: "",
          year: new Date().getFullYear().toString(),
          product_category: "",
          country: "GB",
          description: "",
        });
        setSuccess(false);
        setUploadProgress(0);
      }, 3000);
    } catch (err: any) {
      setError(err.message || "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center">
        <div className="starburst" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-void">
      {/* Header */}
      <header className="border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/admin" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-transmission rounded-sm flex items-center justify-center">
                <span className="font-display text-sm font-bold text-signal">T</span>
              </div>
              <span className="font-display font-bold text-signal">TellyAds</span>
            </Link>
            <Badge variant="transmission">Admin</Badge>
          </div>

          <Link
            href="/admin"
            className="font-mono text-sm text-antenna hover:text-signal transition-colors"
          >
            ← Back to Dashboard
          </Link>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-3xl mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="font-display text-display-md font-bold text-signal mb-2">
            Upload New Ad
          </h1>
          <p className="font-mono text-antenna mb-12">
            Add a new commercial to the TellyAds archive. The video will be processed
            through the RAG pipeline automatically.
          </p>

          {success && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-8 p-4 bg-green-500/10 border border-green-500/30 rounded-lg"
            >
              <p className="font-mono text-sm text-green-400">
                Upload successful! The video has been queued for processing.
              </p>
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-8">
            {/* File upload area */}
            <div>
              <label className="block font-mono text-label uppercase tracking-ultra-wide text-antenna mb-3">
                Video File *
              </label>
              <div
                onClick={() => fileInputRef.current?.click()}
                className={clsx(
                  "relative p-8 border-2 border-dashed rounded-lg cursor-pointer",
                  "transition-colors duration-200",
                  selectedFile
                    ? "border-transmission/50 bg-transmission/5"
                    : "border-white/20 hover:border-white/40"
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="video/*"
                  onChange={handleFileSelect}
                  className="hidden"
                />

                <div className="text-center">
                  {selectedFile ? (
                    <>
                      <p className="font-mono text-signal mb-2">{selectedFile.name}</p>
                      <p className="font-mono text-xs text-antenna">
                        {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="font-mono text-signal mb-2">
                        Click to select a video file
                      </p>
                      <p className="font-mono text-xs text-antenna">
                        MP4, MOV, or AVI up to 500MB
                      </p>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Brand name */}
            <div>
              <label className="block font-mono text-label uppercase tracking-ultra-wide text-antenna mb-2">
                Brand Name *
              </label>
              <input
                type="text"
                name="brand_name"
                value={formData.brand_name}
                onChange={handleInputChange}
                className="w-full px-4 py-3 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission"
                placeholder="e.g., Nike, Coca-Cola"
                required
              />
            </div>

            {/* Product name */}
            <div>
              <label className="block font-mono text-label uppercase tracking-ultra-wide text-antenna mb-2">
                Product / Campaign Name
              </label>
              <input
                type="text"
                name="product_name"
                value={formData.product_name}
                onChange={handleInputChange}
                className="w-full px-4 py-3 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission"
                placeholder="e.g., Air Max, Christmas Campaign"
              />
            </div>

            {/* Year and Category row */}
            <div className="grid grid-cols-2 gap-6">
              <div>
                <label className="block font-mono text-label uppercase tracking-ultra-wide text-antenna mb-2">
                  Year
                </label>
                <input
                  type="number"
                  name="year"
                  value={formData.year}
                  onChange={handleInputChange}
                  min="1950"
                  max={new Date().getFullYear()}
                  className="w-full px-4 py-3 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission"
                />
              </div>

              <div>
                <label className="block font-mono text-label uppercase tracking-ultra-wide text-antenna mb-2">
                  Category
                </label>
                <select
                  name="product_category"
                  value={formData.product_category}
                  onChange={handleInputChange}
                  className="w-full px-4 py-3 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission"
                >
                  <option value="">Select category</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Country */}
            <div>
              <label className="block font-mono text-label uppercase tracking-ultra-wide text-antenna mb-2">
                Country
              </label>
              <select
                name="country"
                value={formData.country}
                onChange={handleInputChange}
                className="w-full px-4 py-3 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission"
              >
                <option value="GB">United Kingdom</option>
                <option value="US">United States</option>
                <option value="AU">Australia</option>
                <option value="CA">Canada</option>
                <option value="IE">Ireland</option>
                <option value="NZ">New Zealand</option>
                <option value="OTHER">Other</option>
              </select>
            </div>

            {/* Description */}
            <div>
              <label className="block font-mono text-label uppercase tracking-ultra-wide text-antenna mb-2">
                Description (Optional)
              </label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleInputChange}
                rows={3}
                className="w-full px-4 py-3 bg-static/50 border border-white/10 rounded font-mono text-signal focus:outline-none focus:ring-2 focus:ring-transmission resize-none"
                placeholder="Brief description of the ad..."
              />
            </div>

            {/* Error message */}
            {error && (
              <div className="p-4 bg-transmission/10 border border-transmission/30 rounded">
                <p className="font-mono text-sm text-transmission">{error}</p>
              </div>
            )}

            {/* Upload progress */}
            {uploading && (
              <div>
                <div className="h-2 bg-static rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-transmission"
                    initial={{ width: 0 }}
                    animate={{ width: `${uploadProgress}%` }}
                    transition={{ duration: 0.3 }}
                  />
                </div>
                <p className="font-mono text-xs text-antenna mt-2">
                  Uploading... {uploadProgress}%
                </p>
              </div>
            )}

            {/* Submit button */}
            <div className="flex gap-4 pt-4">
              <Button
                type="submit"
                variant="primary"
                size="lg"
                disabled={uploading || !selectedFile}
              >
                {uploading ? "Uploading..." : "Upload & Process"}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="lg"
                onClick={() => router.push("/admin")}
              >
                Cancel
              </Button>
            </div>
          </form>
        </motion.div>
      </main>
    </div>
  );
}
