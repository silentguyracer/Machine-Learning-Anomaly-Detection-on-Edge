import numpy as np
import os
import joblib

class NeuralAutoencoder:
    """
    Lightweight Edge Neural Autoencoder for Unsupervised Anomaly Detection
    Architecture: 4 -> 8 -> 2 (Latent Bottleneck) -> 8 -> 4
    Calculates reconstruction error and per-sensor anomaly attribution.
    """
    def __init__(self, input_dim: int = 4, latent_dim: int = 2):
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.trained = False
        
        # Initialize weights with Xavier/Glorot normal
        np.random.seed(42)
        self.W1 = np.random.randn(input_dim, 8) * np.sqrt(2.0 / (input_dim + 8))
        self.b1 = np.zeros(8)
        
        self.W2 = np.random.randn(8, latent_dim) * np.sqrt(2.0 / (8 + latent_dim))
        self.b2 = np.zeros(latent_dim)
        
        self.W3 = np.random.randn(latent_dim, 8) * np.sqrt(2.0 / (latent_dim + 8))
        self.b3 = np.zeros(8)
        
        self.W4 = np.random.randn(8, input_dim) * np.sqrt(2.0 / (8 + input_dim))
        self.b4 = np.zeros(input_dim)
        
        self.threshold = 0.45

    def _relu(self, x):
        return np.maximum(0, x)

    def _relu_grad(self, x):
        return (x > 0).astype(np.float64)

    def encode(self, X: np.ndarray) -> np.ndarray:
        """Projects high-dimensional telemetry into 2D latent bottleneck space (PCA-like)."""
        h1 = self._relu(np.dot(X, self.W1) + self.b1)
        z = np.dot(h1, self.W2) + self.b2
        return z

    def decode(self, z: np.ndarray) -> np.ndarray:
        """Reconstructs telemetry from 2D latent space."""
        h3 = self._relu(np.dot(z, self.W3) + self.b3)
        x_hat = np.dot(h3, self.W4) + self.b4
        return x_hat

    def forward(self, X: np.ndarray):
        h1 = self._relu(np.dot(X, self.W1) + self.b1)
        z = np.dot(h1, self.W2) + self.b2
        h3 = self._relu(np.dot(z, self.W3) + self.b3)
        x_hat = np.dot(h3, self.W4) + self.b4
        return x_hat, z, (h1, h3)

    def fit(self, X: np.ndarray, epochs: int = 80, lr: float = 0.015, batch_size: int = 64):
        N = X.shape[0]
        for epoch in range(epochs):
            indices = np.random.permutation(N)
            X_shuffled = X[indices]
            
            for i in range(0, N, batch_size):
                xb = X_shuffled[i:i+batch_size]
                m = xb.shape[0]
                
                # Forward pass
                h1 = self._relu(np.dot(xb, self.W1) + self.b1)
                z = np.dot(h1, self.W2) + self.b2
                h3 = self._relu(np.dot(z, self.W3) + self.b3)
                x_hat = np.dot(h3, self.W4) + self.b4
                
                # Loss gradient (MSE)
                d_out = 2.0 * (x_hat - xb) / m
                
                # Backprop
                dW4 = np.dot(h3.T, d_out)
                db4 = np.sum(d_out, axis=0)
                
                dh3 = np.dot(d_out, self.W4.T) * self._relu_grad(h3)
                dW3 = np.dot(z.T, dh3)
                db3 = np.sum(dh3, axis=0)
                
                dz = np.dot(dh3, self.W3.T)
                dW2 = np.dot(h1.T, dz)
                db2 = np.sum(dz, axis=0)
                
                dh1 = np.dot(dz, self.W2.T) * self._relu_grad(h1)
                dW1 = np.dot(xb.T, dh1)
                db1 = np.sum(dh1, axis=0)
                
                # Gradient descent step
                self.W4 -= lr * dW4
                self.b4 -= lr * db4
                self.W3 -= lr * dW3
                self.b3 -= lr * db3
                self.W2 -= lr * dW2
                self.b2 -= lr * db2
                self.W1 -= lr * dW1
                self.b1 -= lr * db1
        
        # Calculate normal baseline reconstruction errors to set threshold
        x_hat, _, _ = self.forward(X)
        errors = np.mean((X - x_hat) ** 2, axis=1)
        self.threshold = float(np.percentile(errors, 95))
        self.trained = True

    def predict_sample(self, x: np.ndarray):
        """
        x: shape (4,) scaled features
        Returns: (reconstruction_error, is_anomaly, sensor_attributions, latent_coords)
        """
        if x.ndim == 1:
            x_in = x.reshape(1, -1)
        else:
            x_in = x
            
        x_hat, z, _ = self.forward(x_in)
        
        per_sensor_mse = (x_in[0] - x_hat[0]) ** 2
        total_mse = float(np.mean(per_sensor_mse))
        
        # Calculate percentage attribution per sensor
        sum_mse = float(np.sum(per_sensor_mse))
        if sum_mse > 1e-6:
            attribution = [round(float(val / sum_mse) * 100.0, 1) for val in per_sensor_mse]
        else:
            attribution = [25.0, 25.0, 25.0, 25.0]
            
        is_anomaly = bool(total_mse > self.threshold)
        latent_coords = [round(float(z[0, 0]), 3), round(float(z[0, 1]), 3)]
        
        return total_mse, is_anomaly, attribution, latent_coords

    def save(self, filepath: str):
        joblib.dump(self, filepath)

    @classmethod
    def load(cls, filepath: str):
        return joblib.load(filepath)
