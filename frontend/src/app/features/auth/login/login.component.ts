import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css']
})
export class LoginComponent implements OnInit {
  loginForm: FormGroup;
  error: string | null = null;

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private router: Router,
    private route: ActivatedRoute
  ) {
    this.loginForm = this.fb.group({
      email: ['', [Validators.required]],
      password: ['', [Validators.required]]
    });
  }

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      if (params['code']) {
        this.handleOAuthCallback(params['code']);
      }
    });
  }

  onSubmit() {
    if (this.loginForm.valid) {
      this.error = 'Login manual no implementado. Use Google OAuth.';
    } else {
      this.loginForm.markAllAsTouched();
    }
  }

  loginWithGoogle() {
    this.authService.loginWithGoogle();
  }

  loginAsManager() {
    this.authService.loginAsManager();
  }

  loginAsSalesperson() {
    this.authService.loginAsSalesperson();
  }

  private handleOAuthCallback(code: string) {
    this.authService.handleOAuthCallback(code);
  }
}
